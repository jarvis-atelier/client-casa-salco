"""Mapper File 2 (615s0b.xls) sheet 'Sheet1' -> Articulo.

Espejo del patron de `proveedores_xls.py` (B3) y `etl/mappers/articulos.py`
(DBF). Adaptado al shape del .xls legacy de Casa Salco para articulos
(34843 filas).

## Headers reales del sheet 'Sheet1'

Verificados por xlrd directo sobre el archivo real (codepoints inspeccionados):

    Articulo | Descripcion | Unidad de medida | Proveedor |
    NOMBRE PROVEEDOR | COMPRA | PUBLICO | RUBRO | Grupo |
    MARCA | Marca NOMBRE | GRUPDESC | CATEGORIA

Los acentos en `Articulo` (`Art\xedculo`) y `Descripcion` (`Descripci\xf3n`)
ya estan correctos en utf-8 al leerse — `decode_xls_str` es idempotente
sobre ellos. Los strings literales en este modulo usan los caracteres
reales para que `read_sheet` (que mapea por nombre de header) los matche.

## Mapeo a `app.models.Articulo`

Verificado contra `PROYECTO ERP/backend/app/models/articulo.py`:

| xls column          | Articulo field                        | Notes                                  |
|---------------------|---------------------------------------|----------------------------------------|
| Articulo            | codigo (String(30), unique, NOT NULL) | natural key                            |
| Descripcion         | descripcion (String(255), NOT NULL)   |                                        |
| Unidad de medida    | unidad_medida (UnidadMedidaEnum)      | U/KG/LT/GR/ML -> enum lowercase        |
| Proveedor           | proveedor_principal_id (FK -> proveedores.id) | NULL si no existe + WARN       |
| COMPRA              | costo (Numeric(14,4))                 | 0 permitido                            |
| PUBLICO             | pvp_base (Numeric(14,4))              |                                        |
| RUBRO               | rubro_id (FK -> rubros.id)            | sin-rubro fallback + WARN              |
| Grupo               | familia_id (FK -> familias.id)        | sin-familia fallback + WARN            |
| MARCA               | marca_id                              | NULL ALWAYS (design Section 4)         |
| (derivado)          | descripcion_corta                     | None (no source)                       |
| (derivado)          | iva_porc                              | Decimal("21") default por modelo       |
| (derivado)          | codigo_barras                         | None (RF-01 deferido)                  |
| NOMBRE PROVEEDOR    | --                                    | ignorado (ya en Proveedor.razon_social) |
| Marca NOMBRE        | --                                    | ignorado                               |
| GRUPDESC            | --                                    | preservado en raw_catalog (no modelo)  |
| CATEGORIA           | --                                    | preservado en raw_catalog (no modelo)  |

## Decision 6 — preservacion de valores legacy (Option 3)

`Articulo.observaciones` NO existe en el modelo. Para preservar los textos
crudos `RUBRO`, `Grupo`, `MARCA` (mas `GRUPDESC` / `CATEGORIA` como bonus),
acumulamos en una lista local en `extract`/`load` que se devuelve al caller
junto con el `LoadReport`. El Phase 6 Report writer (B6) consume esta
lista y la surface-a en la seccion "Raw catalog values preserved".

Contract:

    extract(...) -> tuple[Iterator[dict], list]  # rows, legacy_acc placeholder
    # actual implementacion: load() recibe rows + legacy_acc y retorna
    # (LoadReport, list_compra_zero) — ver firma abajo.

Decision: Option 3 (module-local accumulators). NO se toca
`etl/mappers/common.py` (compartido con DBF importer) — separacion limpia.

## Fallbacks `sin-rubro` / `sin-familia`

REQUERIDOS pre-existentes en la DB. `build_fk_caches` los busca y levanta
`RuntimeError` con mensaje claro si faltan — NO los crea on-the-fly (per
orchestrator hard rule B4: "do NOT attempt to create them on-the-fly,
report as blocker").

Si hay que crearlos, opciones (orchestrator decide):
- Agregar al seed `flask seed big` (data/taxonomia.py)
- Correr el DBF importer primero (`etl/import_dbfs.py`) — los crea en
  `etl/mappers/familias_rubros.py:plan()`.
- Agregar una tarea de seed al change actual.

## Idempotencia

`Articulo.codigo` es la natural key. Patron mismo que `proveedores_xls.py`:
build `existing = {a.codigo: a for a in session.query(Articulo).all()}` UNA
vez al inicio, todo el loop trabaja contra ese dict. Re-correr -> inserted=0.

Intra-sheet duplicate codigo: last-wins (consistente con proveedores).

## Junk filter (design Section 6)

- skip si codigo IS None / '' / '0000'
- skip si codigo == descripcion (rows muertas tipo '0000|0000|...')
- skip si descripcion matchea ^test|^prueba|^xxx (case-insensitive)

## --skip-compra-cero (default OFF)

- OFF (default): articulos con COMPRA=0 SE importan con costo=0. Se
  loggean en una lista `compra_zero_acc` para que el Report writer (B6)
  los muestre en la seccion "Articulos con compra=0".
- ON: SE saltan + warn `"compra=0 (--skip-compra-cero)"`.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Iterator
from decimal import Decimal
from pathlib import Path

from app.models import Articulo, Familia, Proveedor, Rubro
from app.models.articulo import UnidadMedidaEnum

from etl.mappers.common import LoadReport, clean_str, decimal_or_zero, sanitize_text
from etl.xls.mappers.common_xls import read_sheet

logger = logging.getLogger("etl.xls.articulos")


# ---------------------------------------------------------------------------
# Header constants (verificados por inspeccion directa de Sheet1).
# ---------------------------------------------------------------------------

COL_CODIGO = "Artículo"
COL_DESCRIPCION = "Descripción"
COL_UNIDAD = "Unidad de medida"
COL_PROVEEDOR = "Proveedor"
COL_NOMBRE_PROVEEDOR = "NOMBRE PROVEEDOR"  # ignored
COL_COMPRA = "COMPRA"
COL_PUBLICO = "PUBLICO"
COL_RUBRO = "RUBRO"
COL_GRUPO = "Grupo"
COL_MARCA = "MARCA"
COL_MARCA_NOMBRE = "Marca NOMBRE"  # ignored
COL_GRUPDESC = "GRUPDESC"
COL_CATEGORIA = "CATEGORIA"


# Codes for fallbacks (must pre-exist in DB; do not auto-create here).
FAMILIA_SIN_CODE = "sin-familia"
RUBRO_SIN_CODE = "sin-rubro"


# Junk patterns para descripcion.
_JUNK_DESC_RE = re.compile(r"^(test|prueba|xxx|asdla|yyy)", re.IGNORECASE)


# Map de unidades legacy del .xls a UnidadMedidaEnum del modelo.
# Los valores reales del Sheet1 son tipicamente single-char (`U`, `K`) o
# 2-char (`UN`, `KG`, `LT`, `GR`, `ML`). Comparacion case-insensitive,
# fallback a `unidad`.
_UNIDAD_MAP: dict[str, UnidadMedidaEnum] = {
    "U": UnidadMedidaEnum.unidad,
    "UN": UnidadMedidaEnum.unidad,
    "KG": UnidadMedidaEnum.kg,
    "K": UnidadMedidaEnum.kg,
    "LT": UnidadMedidaEnum.lt,
    "L": UnidadMedidaEnum.lt,
    "GR": UnidadMedidaEnum.gr,
    "G": UnidadMedidaEnum.gr,
    "ML": UnidadMedidaEnum.ml,
}


def _map_unidad(raw) -> UnidadMedidaEnum:
    """Mapea el string legacy de 'Unidad de medida' a UnidadMedidaEnum.

    Comparacion case-insensitive y trim. Fallback `unidad` si no matchea.
    Usado por `extract` por fila.
    """
    if raw is None:
        return UnidadMedidaEnum.unidad
    s = clean_str(raw)
    if not s:
        return UnidadMedidaEnum.unidad
    return _UNIDAD_MAP.get(s.upper(), UnidadMedidaEnum.unidad)


# ---------------------------------------------------------------------------
# FK caches
# ---------------------------------------------------------------------------

def build_fk_caches(session) -> dict:
    """Construye los caches de FK en memoria para el loop de articulos.

    UNA sola query por entidad — el loop NO consulta la DB por fila.

    Caches:
      - `proveedor`: {Proveedor.codigo (str): Proveedor.id (int)}
      - `familia`:   {Familia.codigo (str): Familia.id (int)}
      - `rubro`:     {(Rubro.codigo (str), Rubro.familia_id (int)): Rubro.id (int)}
        (composite key porque `Rubro.codigo` NO es unique solo — el unique
         constraint es `(familia_id, codigo)`. Verificado en
         `app/models/categorias.py:23-24`.)
      - `sin_familia_id`: int — fallback Familia.id (REQUERIDO)
      - `sin_rubro_id`:   int — fallback Rubro.id bajo sin-familia (REQUERIDO)

    Marca: NO se cachea — `marca_id = NULL` ALWAYS por design Section 4.

    Raises:
      RuntimeError: si `sin-familia` o `sin-rubro` no existen en la DB.
        Per orchestrator hard rule (B4): NO se crean on-the-fly. El caller
        debe asegurarlos via seed (`flask seed big` debe extenderse, o el
        DBF importer debe haber corrido antes).
    """
    proveedor_cache: dict[str, int] = {
        p.codigo: p.id for p in session.query(Proveedor).all()
    }
    familia_cache: dict[str, int] = {
        f.codigo: f.id for f in session.query(Familia).all()
    }
    rubro_cache: dict[tuple[str, int], int] = {
        (r.codigo, r.familia_id): r.id for r in session.query(Rubro).all()
    }

    sin_familia_id = familia_cache.get(FAMILIA_SIN_CODE)
    if sin_familia_id is None:
        raise RuntimeError(
            f"FAMILIA fallback '{FAMILIA_SIN_CODE}' no existe en la DB. "
            "El xls importer la requiere para mapear articulos con `Grupo` "
            "no resoluble. Acciones: (1) extender seed `flask seed big` "
            "para crear la familia, o (2) correr el DBF importer primero "
            "(`etl/import_dbfs.py`) que la crea en `familias_rubros.py:plan()`. "
            "NO se crea on-the-fly por decision del orquestador (B4 hard rule)."
        )

    sin_rubro_key = (RUBRO_SIN_CODE, sin_familia_id)
    sin_rubro_id = rubro_cache.get(sin_rubro_key)
    if sin_rubro_id is None:
        raise RuntimeError(
            f"RUBRO fallback '{RUBRO_SIN_CODE}' bajo familia '{FAMILIA_SIN_CODE}' "
            f"(familia_id={sin_familia_id}) no existe en la DB. "
            "El xls importer lo requiere para mapear articulos con `RUBRO` "
            "no resoluble. Acciones: (1) extender seed `flask seed big`, o "
            "(2) correr el DBF importer primero. NO se crea on-the-fly."
        )

    return {
        "proveedor": proveedor_cache,
        "familia": familia_cache,
        "rubro": rubro_cache,
        "sin_familia_id": sin_familia_id,
        "sin_rubro_id": sin_rubro_id,
    }


# ---------------------------------------------------------------------------
# extract — yieldea rows ya con FK ids resueltos (por cache, no por DB).
# ---------------------------------------------------------------------------

def extract(
    workbook_path: Path | str,
    *,
    sheet_name: str = "Sheet1",
    fk_caches: dict,
    skip_compra_cero: bool = False,
) -> tuple[list[dict], list[tuple], list[tuple]]:
    """Lee Sheet1, aplica junk filter + decode + mapping, y resuelve FKs por cache.

    A diferencia de `proveedores_xls.extract` (que es un generator), aca
    devolvemos eagerly tres listas para que el caller pueda surfacearlas
    al Report writer (B6) sin tener que iterar dos veces.

    Returns:
      `(rows, legacy_catalog, compra_zero)` donde:
        - `rows`: lista de dicts listos para `load()`. Cada dict tiene los
          fields del modelo `Articulo` ya resueltos (FK ids o None) + los
          metadatos `_legacy_*` y `_row` para warnings/auditoria.
        - `legacy_catalog`: lista de tuplas `(codigo, raw_rubro, raw_grupo,
          raw_marca, raw_grupdesc, raw_categoria)`. Consumida por B6 en
          la seccion "Raw catalog values preserved".
        - `compra_zero`: lista de tuplas `(codigo, descripcion)` para
          articulos con COMPRA=0 (independientemente de si fueron
          saltados o importados — el flag determina cual). Consumida por B6
          en la seccion "Articulos con compra=0".

    Side effects: LOG (info/warn) sobre rows saltadas (junk filter,
      skip_compra_cero=True). El report final lo arma `load()`.

    FK resolution rules (per design Section 4):
      - Proveedor: cache.get(codigo). Si no existe -> None + WARN.
      - Familia (Grupo): cache.get(codigo). Si no existe -> sin_familia_id + WARN.
      - Rubro: cache.get((codigo, familia_id)) — composite key. Si no existe
        -> sin_rubro_id (bajo sin_familia_id) + WARN.
      - Marca: NULL ALWAYS, sin warn (es by design).

    Args:
      skip_compra_cero: Si True, articulos con COMPRA=0 son saltados aca
        mismo (no llegan al `load()`); igual entran a `compra_zero` para
        auditoria del report.
    """
    rows: list[dict] = []
    legacy_catalog: list[tuple] = []
    compra_zero: list[tuple] = []

    proveedor_cache: dict[str, int] = fk_caches["proveedor"]
    familia_cache: dict[str, int] = fk_caches["familia"]
    rubro_cache: dict[tuple[str, int], int] = fk_caches["rubro"]
    sin_familia_id: int = fk_caches["sin_familia_id"]
    sin_rubro_id: int = fk_caches["sin_rubro_id"]

    # `read_sheet` ya aplica `decode_xls_str` a cada celda string ANTES
    # de yieldear. row_idx empieza en 2 (fila 1 = header, consumida).
    path_str = str(workbook_path)
    for row_idx, row in enumerate(read_sheet(path_str, sheet_name), start=2):
        codigo_raw = row.get(COL_CODIGO)
        descripcion_raw = row.get(COL_DESCRIPCION)

        codigo = clean_str(codigo_raw)
        descripcion = sanitize_text(descripcion_raw, max_len=255)

        # Junk: codigo vacio / '0000' / None
        if codigo is None or codigo == "" or codigo == "0000":
            logger.info(
                "row=%d skip codigo=%r reason='codigo vacio o 0000'",
                row_idx, codigo_raw,
            )
            continue

        # Junk: codigo == descripcion (rows muertas '0000|0000|...')
        if descripcion is not None and codigo == descripcion:
            logger.info(
                "row=%d skip codigo=%r reason='codigo == descripcion'",
                row_idx, codigo,
            )
            continue

        # Junk: descripcion matchea patrones test/prueba/xxx
        if descripcion and _JUNK_DESC_RE.match(descripcion):
            logger.info(
                "row=%d skip codigo=%r desc=%r reason='descripcion matches test/prueba/xxx'",
                row_idx, codigo, descripcion,
            )
            continue

        # Decimales (COMPRA / PUBLICO). decimal_or_zero acepta float/int/str/None.
        compra_raw = row.get(COL_COMPRA)
        publico_raw = row.get(COL_PUBLICO)
        costo = decimal_or_zero(compra_raw, places=4)
        pvp_base = decimal_or_zero(publico_raw, places=4)

        # Descripcion fallback si quedo vacia (pero el codigo es valido):
        # usa "Articulo {codigo}" como minimo para no violar NOT NULL.
        desc_for_db = descripcion or f"Articulo {codigo}"

        # Capturar raw catalog values ANTES de resolver FKs (Decision 6).
        raw_rubro = clean_str(row.get(COL_RUBRO))
        raw_grupo = clean_str(row.get(COL_GRUPO))
        raw_marca = clean_str(row.get(COL_MARCA))
        raw_grupdesc = clean_str(row.get(COL_GRUPDESC))
        raw_categoria = clean_str(row.get(COL_CATEGORIA))

        # Acumular para el Report writer (B6). Siempre — no solo cuando
        # hay fallback — para que el reporte tenga el catalogo completo.
        legacy_catalog.append(
            (codigo, raw_rubro, raw_grupo, raw_marca, raw_grupdesc, raw_categoria)
        )

        # COMPRA=0 audit (default OFF importa igual; ON saltea).
        if costo == Decimal("0"):
            compra_zero.append((codigo, desc_for_db))
            if skip_compra_cero:
                logger.info(
                    "row=%d skip codigo=%r reason='compra=0 (--skip-compra-cero)'",
                    row_idx, codigo,
                )
                continue

        # FK: proveedor. Cache lookup; si missing -> None + WARN logueado
        # como un `_warn` para que `load` lo propague al LoadReport.
        proveedor_codigo_raw = clean_str(row.get(COL_PROVEEDOR))
        warns: list[str] = []
        proveedor_id: int | None = None
        if proveedor_codigo_raw:
            proveedor_id = proveedor_cache.get(proveedor_codigo_raw)
            if proveedor_id is None:
                warns.append(
                    f"row {row_idx}: proveedor codigo "
                    f"{proveedor_codigo_raw!r} not found, set NULL"
                )

        # FK: familia (mapeada desde 'Grupo'). Si missing -> sin-familia + WARN.
        familia_id: int = sin_familia_id
        if raw_grupo:
            cached = familia_cache.get(raw_grupo)
            if cached is not None:
                familia_id = cached
            else:
                warns.append(
                    f"row {row_idx}: grupo (familia) {raw_grupo!r} not found, "
                    "fallback sin-familia"
                )
        else:
            warns.append(
                f"row {row_idx}: grupo (familia) vacio, fallback sin-familia"
            )

        # FK: rubro. Composite key (codigo, familia_id). Si missing ->
        # sin-rubro (bajo sin-familia) + WARN. Nota: si la familia cayo a
        # sin-familia, automaticamente el rubro es buscado bajo esa fam,
        # con lo cual lo mas probable es que tambien caiga al fallback.
        rubro_id: int = sin_rubro_id
        if raw_rubro:
            rubro_id_cached = rubro_cache.get((raw_rubro, familia_id))
            if rubro_id_cached is not None:
                rubro_id = rubro_id_cached
            else:
                warns.append(
                    f"row {row_idx}: rubro {raw_rubro!r} (familia_id={familia_id}) "
                    "not found, fallback sin-rubro"
                )
        else:
            warns.append(
                f"row {row_idx}: rubro vacio, fallback sin-rubro"
            )

        # Marca: NULL ALWAYS (no warn).

        rows.append({
            "codigo": codigo,
            "descripcion": desc_for_db,
            "descripcion_corta": None,
            "unidad_medida": _map_unidad(row.get(COL_UNIDAD)),
            "proveedor_principal_id": proveedor_id,
            "familia_id": familia_id,
            "rubro_id": rubro_id,
            "marca_id": None,  # by design
            "costo": costo,
            "pvp_base": pvp_base,
            # iva_porc, codigo_barras, controla_stock/vencimiento -> usar
            # defaults del modelo (no overrideamos en INSERT).
            "_warns": warns,
            "_row": row_idx,
        })

    return rows, legacy_catalog, compra_zero


# ---------------------------------------------------------------------------
# load — upsert idempotente por Articulo.codigo
# ---------------------------------------------------------------------------

def load(
    session,
    rows: Iterable[dict],
    *,
    batch_size: int = 1000,
) -> LoadReport:
    """Upsert idempotente de Articulo por `codigo` (natural key).

    Patron mismo que `proveedores_xls.load`:
      - `existing = {a.codigo: a for a in session.query(Articulo).all()}` UNA vez.
      - `codigo` no en existing -> INSERT (session.add).
      - `codigo` en existing -> UPDATE in-place de los campos provistos.
      - Sin deltas -> SKIP.
      - Flush cada `batch_size` rows (default 1000).

    Update path (campos overrideados):
      `descripcion`, `costo`, `pvp_base`, `unidad_medida`,
      `proveedor_principal_id`, `rubro_id`, `familia_id`.

    Update path NO toca:
      `marca_id` (siempre NULL en el xls — preservar marcas asignadas
      manualmente o por DBF importer si las hubiera).
      `descripcion_corta` (None en xls — no machacar si el DBF lo lleno).
      `codigo_barras`, `iva_porc`, controles de stock — no overrideamos.

    Insert path: crea Articulo con todos los campos mapeados; `marca_id=None`,
    `descripcion_corta=None`. El modelo aplica defaults para `iva_porc=21`,
    `controla_stock=True`, `controla_vencimiento=False`, `activo=True`.

    Intra-sheet duplicate codigo: last-wins. La 2da ocurrencia entra por
    rama UPDATE (porque el 1er INSERT ya esta en `existing`) y sobrescribe.
    Tambien se loguea WARN.
    """
    report = LoadReport(entity="articulos_xls")
    report.start()

    existing: dict[str, Articulo] = {
        a.codigo: a for a in session.query(Articulo).all()
    }
    seen_in_run: set[str] = set()
    pending_flush = 0

    # Update fields que SI machacamos del xls (para evitar re-listarlos).
    UPDATE_FIELDS = (
        "descripcion",
        "costo",
        "pvp_base",
        "unidad_medida",
        "proveedor_principal_id",
        "familia_id",
        "rubro_id",
    )

    for row in rows:
        report.read += 1
        codigo = row["codigo"]
        warns = row.pop("_warns", [])
        row_idx = row.pop("_row", None)

        # Surface FK warns generados en `extract`.
        for w in warns:
            report.warn(codigo, w)

        # Intra-sheet duplicate detection.
        if codigo in seen_in_run:
            report.warn(
                codigo,
                f"row {row_idx}: intra-sheet duplicate codigo (last-wins)",
            )
        seen_in_run.add(codigo)

        try:
            current = existing.get(codigo)
            if current is None:
                # INSERT path.
                articulo = Articulo(
                    codigo=codigo,
                    descripcion=row["descripcion"],
                    descripcion_corta=row["descripcion_corta"],
                    unidad_medida=row["unidad_medida"],
                    proveedor_principal_id=row["proveedor_principal_id"],
                    familia_id=row["familia_id"],
                    rubro_id=row["rubro_id"],
                    marca_id=None,  # by design
                    costo=row["costo"],
                    pvp_base=row["pvp_base"],
                    activo=True,
                )
                session.add(articulo)
                existing[codigo] = articulo
                report.inserted += 1
                pending_flush += 1
            else:
                # UPDATE path (idempotente).
                changed = False
                for key in UPDATE_FIELDS:
                    new_value = row[key]
                    old = getattr(current, key)
                    # Compare Decimals con .compare() para evitar drift por
                    # representacion (ej. Decimal('0.00') vs Decimal('0')).
                    if isinstance(new_value, Decimal) and isinstance(old, Decimal):
                        if old.compare(new_value) != Decimal("0"):
                            setattr(current, key, new_value)
                            changed = True
                    elif old != new_value:
                        setattr(current, key, new_value)
                        changed = True
                if changed:
                    report.updated += 1
                    pending_flush += 1
                else:
                    report.skipped += 1
        except Exception as exc:  # pragma: no cover - salvaguarda defensiva
            report.failed += 1
            report.warn(codigo, f"error al cargar: {exc}")

        if pending_flush >= batch_size:
            session.flush()
            pending_flush = 0

    if pending_flush:
        session.flush()

    report.finish()
    return report
