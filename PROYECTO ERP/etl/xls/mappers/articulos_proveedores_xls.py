"""Mapper File 1 (h00ugz.xls) sheet 'RELACION PRODUCTOS PROVEEDOR' -> ArticuloProveedor.

Espejo del patron `proveedores_xls.py` (B3) y `articulos_xls.py` (B4),
adaptado a la relacion M2M Articulo <-> Proveedor con metadata
(`codigo_proveedor`, `costo_proveedor`).

## Headers reales (verificados via xlrd directo)

Sheet `RELACION PRODUCTOS PROVEEDOR`, 43433 nrows (1 header + 43432 data),
5 cols. Headers SIN acentos y con TRAILING SPACES en `nombre del proveedor `
y `cantidad ` (verificado por inspeccion de codepoints):

    codigo articulo | codigo proveedor | nombre del proveedor  |
    codigo del producto x el proveedor | cantidad

`read_sheet` aplica `decode_xls_str` a cada celda string ANTES de yieldear,
asi que los headers llegan tal cual (ya en utf-8 ASCII puro). Los strings
literales en este modulo usan los mismos espacios para que el dict-key
match.

## Mapeo a `app.models.ArticuloProveedor`

Verificado contra `PROYECTO ERP/backend/app/models/articulo.py:98-118`:

| xls column                          | Field on ArticuloProveedor          | Notes                                       |
|-------------------------------------|--------------------------------------|---------------------------------------------|
| codigo articulo                     | articulo_id (FK -> articulos.id)    | resuelto via cache `articulo_codigo->id`   |
| codigo proveedor                    | proveedor_id (FK -> proveedores.id) | resuelto via cache `proveedor_codigo->id`  |
| nombre del proveedor                | --                                  | ignored (ya en `Proveedor.razon_social`)    |
| codigo del producto x el proveedor  | codigo_proveedor (String(50))       | el codigo que el proveedor usa para el item |
| cantidad                            | cantidad_por_pack (Numeric(10,3))   | re-read en Change B (xls-empaquetados); invalid/None -> Decimal("1") |
| (derivado)                          | costo_proveedor (Numeric(14,4))     | default Decimal(0); xls no provee fuente   |

`UniqueConstraint("articulo_id", "proveedor_id", name="uq_artprov_art_prov")`
-> natural key compuesta para idempotencia.

## Decision 6 (Change B update) — `cantidad` RE-READ a `cantidad_por_pack`

En el change original `importacion-xls-legacy` la columna `cantidad` fue
DROPPED (el modelo no tenia campo destino). En Change B
(`xls-empaquetados-y-presentaciones`) el modelo `ArticuloProveedor` recibio
`cantidad_por_pack: Numeric(10,3) NOT NULL DEFAULT 1` (migration
`f6a7b8c9d0e1`), y este mapper ahora la re-lee:

- Source col: `'cantidad '` (TRAILING SPACE — verificado).
- Target field: `ArticuloProveedor.cantidad_por_pack`.
- Conversion: `decimal_or_zero(value, places=3)`; valores `None`/`0`/invalid
  caen al default semantico `Decimal("1")` (matchea el server_default).
- Last-wins en los 436 (articulo_id, proveedor_id) duplicates intra-sheet.

## FK resolution rules

A diferencia de `articulos_xls` (donde proveedor missing -> NULL +
WARN), aca AMBAS FKs son NOT NULL en el modelo y existe el unique
constraint `(articulo_id, proveedor_id)`. Por lo tanto: si CUALQUIER FK
no resuelve -> SKIP fila + WARN. NO se inserta una fila con FKs en NULL
porque el constraint la rechazaria.

Caches build-once-up-front (UNA query por entidad):
- `articulo_codigo -> id`
- `proveedor_codigo -> id`

Loop NO consulta DB por fila.

## Junk filter (design Section 6)

- skip si `codigo articulo` IS None / '' / '0000'
- skip si `codigo proveedor` IS None / '' / '0000'
- skip si `codigo articulo == codigo proveedor` (rows test del legacy)

## Idempotencia

Composite natural key `(articulo_id, proveedor_id)` per
UniqueConstraint del modelo. Patron mismo que los otros mappers:
build `existing` dict UNA vez al inicio. Re-correr -> inserted=0.

UPDATE path machaca `codigo_proveedor` y `cantidad_por_pack` (Change B).
`costo_proveedor` queda en 0 default y NO se toca para preservar el valor
que el DBF importer pueda haber cargado desde ARTIPROV.PRCO. Sin deltas
-> SKIP.

Intra-sheet duplicate `(articulo, proveedor)`: last-wins (consistente con
los otros mappers).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from decimal import Decimal
from pathlib import Path

from app.models import Articulo, ArticuloProveedor, Proveedor

from etl.mappers.common import LoadReport, clean_str, decimal_or_zero
from etl.xls.mappers.common_xls import read_sheet

logger = logging.getLogger("etl.xls.articulos_proveedores")


# ---------------------------------------------------------------------------
# Header constants — VERIFICADOS via xlrd directo sobre el archivo real.
# Los headers son ASCII puro pero `nombre del proveedor ` y `cantidad ` tienen
# TRAILING SPACE — preservarlo o el dict-lookup falla.
# ---------------------------------------------------------------------------

COL_CODIGO_ARTICULO = "codigo articulo"
COL_CODIGO_PROVEEDOR = "codigo proveedor"
COL_NOMBRE_PROVEEDOR = "nombre del proveedor "  # ignored; trailing space
COL_CODIGO_ALTERNO = "codigo del producto x el proveedor"
COL_CANTIDAD = "cantidad "  # RE-READ in Change B -> cantidad_por_pack; trailing space


# Sheet por defecto en el File 1 (h00ugz.xls).
DEFAULT_SHEET = "RELACION PRODUCTOS PROVEEDOR"


# ---------------------------------------------------------------------------
# FK caches
# ---------------------------------------------------------------------------

def build_fk_caches(session) -> dict:
    """Construye caches `articulo_codigo->id` y `proveedor_codigo->id`.

    UNA sola query por entidad — el loop NO consulta la DB por fila.

    A diferencia de `articulos_xls.build_fk_caches`, aca NO hay fallbacks
    `sin-*` ni se levanta `RuntimeError`. Si falta un articulo o proveedor,
    el extract loguea WARN y la fila se SKIPea — la presencia de los FKs
    es "soft" requerida (el constraint del modelo lo es "hard").
    """
    articulo_cache: dict[str, int] = {
        a.codigo: a.id for a in session.query(Articulo).all()
    }
    proveedor_cache: dict[str, int] = {
        p.codigo: p.id for p in session.query(Proveedor).all()
    }
    return {
        "articulo": articulo_cache,
        "proveedor": proveedor_cache,
    }


# ---------------------------------------------------------------------------
# extract
# ---------------------------------------------------------------------------

def extract(
    workbook_path: Path | str,
    *,
    sheet_name: str = DEFAULT_SHEET,
    fk_caches: dict,
) -> Iterator[dict]:
    """Itera la sheet RELACION PRODUCTOS PROVEEDOR y yieldea dicts normalizados.

    Junk filter (design Section 6):
      - skip si `codigo articulo` IS None / '' / '0000'
      - skip si `codigo proveedor` IS None / '' / '0000'
      - skip si `codigo articulo == codigo proveedor` (rows test del legacy)

    FK resolution (design Section 4 + Decision 5.1):
      - articulo_codigo -> cache.get; missing -> SKIP + WARN
      - proveedor_codigo -> cache.get; missing -> SKIP + WARN
      - NO se insertan filas con FKs en NULL (el unique constraint
        `(articulo_id, proveedor_id)` requiere ambos NOT NULL).

    `cantidad` (col `'cantidad '` con trailing space) se RE-LEE en Change B
    y se persiste en `ArticuloProveedor.cantidad_por_pack` (Numeric(10,3)).
    Valores `None`/`0`/invalid caen al default `Decimal("1")` (matchea el
    server_default del modelo).

    Yieldea dicts con keys:
      articulo_id, proveedor_id, codigo_proveedor, cantidad_por_pack, _row

    `_row` es el numero de fila excel (1-indexed, header=1) para warnings.
    """
    articulo_cache: dict[str, int] = fk_caches["articulo"]
    proveedor_cache: dict[str, int] = fk_caches["proveedor"]

    logger.info(
        "extract sheet=%r articulo_cache_size=%d proveedor_cache_size=%d",
        sheet_name, len(articulo_cache), len(proveedor_cache),
    )

    path_str = str(workbook_path)
    for row_idx, row in enumerate(read_sheet(path_str, sheet_name), start=2):
        # row_idx empieza en 2 porque la fila 1 es header (consumida por read_sheet);
        # la primera data row corresponde a Excel #2 (1-indexed).

        codigo_articulo = clean_str(row.get(COL_CODIGO_ARTICULO))
        codigo_proveedor_fk = clean_str(row.get(COL_CODIGO_PROVEEDOR))

        # Junk: codigo articulo vacio / '0000'
        if codigo_articulo is None or codigo_articulo == "" or codigo_articulo == "0000":
            logger.info(
                "row=%d skip articulo=%r reason='codigo articulo vacio o 0000'",
                row_idx, codigo_articulo,
            )
            continue

        # Junk: codigo proveedor vacio / '0000'
        if codigo_proveedor_fk is None or codigo_proveedor_fk == "" or codigo_proveedor_fk == "0000":
            logger.info(
                "row=%d skip articulo=%r proveedor=%r reason='codigo proveedor vacio o 0000'",
                row_idx, codigo_articulo, codigo_proveedor_fk,
            )
            continue

        # Junk: codigo articulo == codigo proveedor (rows test del legacy)
        if codigo_articulo == codigo_proveedor_fk:
            logger.info(
                "row=%d skip codigo=%r reason='codigo articulo == codigo proveedor (test row)'",
                row_idx, codigo_articulo,
            )
            continue

        # FK resolution. Si falta CUALQUIERA -> SKIP + WARN (no NULL inserts).
        articulo_id = articulo_cache.get(codigo_articulo)
        if articulo_id is None:
            logger.warning(
                "row=%d skip — articulo codigo=%r not found in DB (skipping)",
                row_idx, codigo_articulo,
            )
            yield {
                "_skip": True,
                "_row": row_idx,
                "_skip_reason": (
                    f"row {row_idx}: articulo codigo {codigo_articulo!r} not found, skipped"
                ),
                "_skip_key": f"{codigo_articulo}/{codigo_proveedor_fk}",
            }
            continue

        proveedor_id = proveedor_cache.get(codigo_proveedor_fk)
        if proveedor_id is None:
            logger.warning(
                "row=%d skip — proveedor codigo=%r not found in DB (skipping)",
                row_idx, codigo_proveedor_fk,
            )
            yield {
                "_skip": True,
                "_row": row_idx,
                "_skip_reason": (
                    f"row {row_idx}: proveedor codigo {codigo_proveedor_fk!r} not found, skipped"
                ),
                "_skip_key": f"{codigo_articulo}/{codigo_proveedor_fk}",
            }
            continue

        # `codigo_proveedor` field on the model = supplier's code for the article
        # (i.e. xls column `codigo del producto x el proveedor`). Distinct from
        # the FK lookup `codigo_proveedor` which was the proveedor maestro code.
        codigo_alterno = clean_str(row.get(COL_CODIGO_ALTERNO), max_len=50)

        # `cantidad` re-read (Change B). Invalid/None/0 -> Decimal("1") matching
        # the model's server_default.
        cantidad_raw = row.get(COL_CANTIDAD)
        cantidad_por_pack = decimal_or_zero(cantidad_raw, places=3)
        if cantidad_por_pack <= Decimal("0"):
            cantidad_por_pack = Decimal("1")

        yield {
            "articulo_id": articulo_id,
            "proveedor_id": proveedor_id,
            "codigo_proveedor": codigo_alterno,
            "cantidad_por_pack": cantidad_por_pack,
            "_row": row_idx,
        }


# ---------------------------------------------------------------------------
# load — upsert idempotente por (articulo_id, proveedor_id)
# ---------------------------------------------------------------------------

def load(
    session,
    rows: Iterable[dict],
    *,
    batch_size: int = 1000,
) -> LoadReport:
    """Upsert idempotente de ArticuloProveedor por `(articulo_id, proveedor_id)`.

    Patron mismo que `articulos_xls.load`:
      - `existing = {(ap.articulo_id, ap.proveedor_id): ap for ap in
        session.query(ArticuloProveedor).all()}` UNA vez al inicio.
      - Key no en existing -> INSERT (session.add).
      - Key en existing -> UPDATE in-place de `codigo_proveedor` si difiere.
      - Sin deltas -> SKIP.
      - Flush cada `batch_size` rows (default 1000).

    Update path: machaca `codigo_proveedor` y `cantidad_por_pack` (Change B,
    last-wins via Decimal.compare). NO toca `costo_proveedor` (el xls no
    provee fuente — preservar valor cargado por DBF importer desde
    ARTIPROV.PRCO si lo hubiera) ni `ultimo_ingreso`.

    Insert path: crea `ArticuloProveedor` con `costo_proveedor=Decimal(0)`
    default, `codigo_proveedor` del xls (puede ser None), y
    `cantidad_por_pack` del xls (default `Decimal("1")` si invalid/None).

    Skip rows from extract: las filas con `_skip=True` son contabilizadas
    como `failed` con su `_skip_reason` propagado al WarningRecord (mismo
    contrato que `etl/mappers/articulos_proveedores.py` DBF — no abortan).

    Intra-sheet duplicate `(articulo_id, proveedor_id)`: last-wins. La 2da
    ocurrencia entra por rama UPDATE (porque el 1er INSERT ya esta en
    `existing`) y sobrescribe. Tambien se loguea WARN.
    """
    report = LoadReport(entity="articulos_proveedores_xls")
    report.start()

    existing: dict[tuple[int, int], ArticuloProveedor] = {
        (ap.articulo_id, ap.proveedor_id): ap
        for ap in session.query(ArticuloProveedor).all()
    }
    seen_in_run: set[tuple[int, int]] = set()
    pending_flush = 0

    for row in rows:
        report.read += 1

        # Skip rows (FK miss) — surface as `failed` per DBF importer convention.
        if row.get("_skip"):
            report.failed += 1
            report.warn(row.get("_skip_key", "?"), row.get("_skip_reason", "skipped"))
            continue

        articulo_id = row["articulo_id"]
        proveedor_id = row["proveedor_id"]
        codigo_proveedor_field = row.get("codigo_proveedor")
        cantidad_por_pack = row.get("cantidad_por_pack", Decimal("1"))
        row_idx = row.get("_row")
        key = (articulo_id, proveedor_id)
        identifier = f"{articulo_id}/{proveedor_id}"

        # Intra-sheet duplicate detection.
        if key in seen_in_run:
            report.warn(
                identifier,
                f"row {row_idx}: intra-sheet duplicate (articulo_id, proveedor_id) (last-wins)",
            )
        seen_in_run.add(key)

        try:
            current = existing.get(key)
            if current is None:
                # INSERT path.
                ap = ArticuloProveedor(
                    articulo_id=articulo_id,
                    proveedor_id=proveedor_id,
                    codigo_proveedor=codigo_proveedor_field,
                    costo_proveedor=Decimal("0"),
                    cantidad_por_pack=cantidad_por_pack,
                )
                session.add(ap)
                existing[key] = ap
                report.inserted += 1
                pending_flush += 1
            else:
                # UPDATE path (idempotente). `codigo_proveedor` y
                # `cantidad_por_pack` (Change B).
                changed = False
                if current.codigo_proveedor != codigo_proveedor_field:
                    current.codigo_proveedor = codigo_proveedor_field
                    changed = True
                # Decimal compare via .compare() to avoid drift por representacion
                # (mirror articulos_xls UPDATE pattern).
                old_cant = current.cantidad_por_pack
                if isinstance(old_cant, Decimal) and isinstance(cantidad_por_pack, Decimal):
                    if old_cant.compare(cantidad_por_pack) != Decimal("0"):
                        current.cantidad_por_pack = cantidad_por_pack
                        changed = True
                elif old_cant != cantidad_por_pack:
                    current.cantidad_por_pack = cantidad_por_pack
                    changed = True
                # `costo_proveedor` NO se toca (preserva DBF / valores manuales).
                if changed:
                    report.updated += 1
                    pending_flush += 1
                else:
                    report.skipped += 1
        except Exception as exc:  # pragma: no cover - salvaguarda defensiva
            report.failed += 1
            report.warn(identifier, f"error al cargar: {exc}")

        if pending_flush >= batch_size:
            session.flush()
            pending_flush = 0

    if pending_flush:
        session.flush()

    report.finish()
    return report
