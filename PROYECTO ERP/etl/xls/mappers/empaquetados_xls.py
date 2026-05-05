"""Mapper File 1 (h00ugz.xls) sheet 'EMPAQUETADOS DE PRODUCTOS' -> ArticuloCodigo.

Espejo del patron de `articulos_xls.py` y `articulos_proveedores_xls.py`,
adaptado a la sheet EMPAQUETADOS (22682 rows segun B1 audit) cuya carga
puebla `articulo_codigos` con tipos `principal/alterno/empaquetado` segun
la heuristica isolada en `_tipo_heuristic.py` (B3).

## Headers reales del sheet 'EMPAQUETADOS DE PRODUCTOS'

Verificados via xlrd directo en B1 (Phase 1 pre-flight, observation #561):

    Codigo | Articulo | Cantidad

NO trailing spaces. Los headers son ASCII puro / sin acentos relevantes;
`decode_xls_str` los pasa intactos. El sheet name TIENE espacios:
`'EMPAQUETADOS DE PRODUCTOS'`.

## Mapeo a `app.models.ArticuloCodigo`

Verificado contra `backend/app/models/articulo_codigo.py`:

| xls column | ArticuloCodigo field          | Notes                                  |
|-----------|--------------------------------|----------------------------------------|
| Codigo    | codigo (String(50), NOT NULL)  | el codigo de barras / empaquetado      |
| Articulo  | articulo_id (FK -> articulos.id) | resuelto via cache `articulo_codigo->id` |
| Cantidad  | (drives heuristic)             | Numeric(10,3); informa la asignacion   |
|           | tipo (TipoCodigoArticuloEnum)  | asignado por `_tipo_heuristic.assign_tipos` |

`UniqueConstraint("articulo_id", "codigo", name="uq_articulo_codigo")`
-> natural key compuesta para idempotencia.

## Heuristica `tipo`

NO se asigna en este mapper. Se delega 100% a
`_tipo_heuristic.assign_tipos(rows)` (B3, observation #561) que necesita
TODAS las rows agrupadas por `codigo_articulo` para decidir
`principal/alterno/empaquetado/alterno-invalid`. Por eso `extract` retorna
`list[dict]` (eager) en vez de generator: el caller debe pasarle la lista
completa a `assign_tipos` antes de `load`.

## FK resolution rules

`Articulo.codigo` es la natural key. Si CUALQUIER `codigo articulo` no
resuelve -> SKIP fila + WARN. NO se inserta una fila con FK NULL (el
constraint del modelo lo prohibe).

Cache build-once-up-front (UNA query):
- `articulo_codigo -> id`

## Junk filter

- skip si `Codigo` IS None / '' / '0000' (B1 audit: 0 junk en la sheet,
  pero defensivo igual).

## Idempotencia

`(articulo_id, codigo)` per UniqueConstraint del modelo. Patron mismo que
los otros mappers: build `existing` dict UNA vez al inicio.
- INSERT path: crea ArticuloCodigo con `articulo_id`, `codigo`, `tipo`.
- UPDATE path: solo machaca `tipo` si difiere (last-wins). Nota: Change A
  backfilleo `tipo='principal'` para los codigos legacy; EMPAQUETADOS
  puede re-clasificar y la rama UPDATE lo refleja idempotentemente.
- Sin delta -> SKIP.

Intra-sheet duplicate `(articulo_id, codigo)`: last-wins (consistente con
los otros mappers).
"""
from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

from app.models import Articulo
from app.models.articulo_codigo import ArticuloCodigo

from etl.mappers.common import LoadReport, clean_str
from etl.xls.mappers._tipo_heuristic import assign_tipos
from etl.xls.mappers.common_xls import read_sheet

logger = logging.getLogger("etl.xls.empaquetados")


# ---------------------------------------------------------------------------
# Header constants — VERIFICADOS via B1 audit (observation #561).
# ASCII puro, sin trailing spaces.
# ---------------------------------------------------------------------------

COL_CODIGO = "Codigo"
COL_ARTICULO = "Articulo"
COL_CANTIDAD = "Cantidad"


# Sheet name CON espacios (verificado).
DEFAULT_SHEET = "EMPAQUETADOS DE PRODUCTOS"


# ---------------------------------------------------------------------------
# FK caches
# ---------------------------------------------------------------------------

def build_fk_caches(session) -> dict:
    """Construye cache `articulo_codigo->id`.

    UNA sola query — el loop NO consulta la DB por fila. Mismo patron que
    `articulos_proveedores_xls.build_fk_caches` (sin fallbacks `sin-*`).
    """
    articulo_cache: dict[str, int] = {
        a.codigo: a.id for a in session.query(Articulo).all()
    }
    return {
        "articulo": articulo_cache,
    }


# ---------------------------------------------------------------------------
# extract — yieldea rows ya con FK ids resueltos y `tipo` asignado.
# ---------------------------------------------------------------------------

def extract(
    workbook_path: Path | str,
    *,
    sheet_name: str = DEFAULT_SHEET,
    fk_caches: dict,
) -> tuple[list[dict], list[dict]]:
    """Lee la sheet EMPAQUETADOS, resuelve FK por cache, y aplica heuristica.

    A diferencia de `articulos_proveedores_xls.extract` (generator), aca
    devolvemos eagerly DOS listas porque `assign_tipos` necesita TODAS las
    filas agrupadas por `codigo_articulo` ANTES de poder decidir el `tipo`.

    Returns:
      `(rows_with_tipo, skipped)` donde:
        - `rows_with_tipo`: lista de dicts listos para `load()`. Cada dict
          tiene `articulo_id`, `codigo`, `tipo` (TipoCodigoArticuloEnum) y
          metadata `_row` para warnings/auditoria.
        - `skipped`: lista de dicts `{_row, codigo, codigo_articulo, reason}`
          para WARN en el LoadReport (FK miss / junk).

    Side effects: LOG (info/warn) sobre rows saltadas. El report final lo
      arma `load()`.

    FK resolution rules:
      - articulo_codigo -> cache.get; missing -> SKIP + WARN (no NULL inserts).

    Junk filter:
      - skip si `Codigo` (codigo del empaquetado/codigo de barras) IS
        None / '' / '0000'.

    `Cantidad` se preserva en el dict intermedio (key 'cantidad') asi
    `assign_tipos` la consume; tras el grouping NO se persiste como columna
    (el modelo `ArticuloCodigo` no tiene campo numerico — el `tipo` es la
    proyeccion de la cantidad sobre el grupo).
    """
    articulo_cache: dict[str, int] = fk_caches["articulo"]

    logger.info(
        "extract sheet=%r articulo_cache_size=%d",
        sheet_name, len(articulo_cache),
    )

    pre_heuristic_rows: list[dict] = []
    skipped: list[dict] = []

    path_str = str(workbook_path)
    for row_idx, row in enumerate(read_sheet(path_str, sheet_name), start=2):
        # row_idx empieza en 2 porque la fila 1 es header (consumida por read_sheet).

        codigo = clean_str(row.get(COL_CODIGO), max_len=50)
        codigo_articulo = clean_str(row.get(COL_ARTICULO))
        cantidad_raw = row.get(COL_CANTIDAD)

        # Junk: codigo empaquetado vacio / '0000' / None
        if codigo is None or codigo == "" or codigo == "0000":
            logger.info(
                "row=%d skip codigo=%r articulo=%r reason='codigo empaquetado vacio o 0000'",
                row_idx, codigo, codigo_articulo,
            )
            skipped.append({
                "_row": row_idx,
                "codigo": codigo,
                "codigo_articulo": codigo_articulo,
                "reason": (
                    f"row {row_idx}: codigo empaquetado vacio/0000, skipped (junk)"
                ),
            })
            continue

        # FK resolution.
        if codigo_articulo is None or codigo_articulo == "":
            logger.warning(
                "row=%d skip codigo=%r — codigo articulo vacio",
                row_idx, codigo,
            )
            skipped.append({
                "_row": row_idx,
                "codigo": codigo,
                "codigo_articulo": codigo_articulo,
                "reason": (
                    f"row {row_idx}: codigo articulo vacio (codigo={codigo!r}), skipped"
                ),
            })
            continue

        articulo_id = articulo_cache.get(codigo_articulo)
        if articulo_id is None:
            logger.warning(
                "row=%d skip codigo=%r — articulo codigo=%r not found in DB",
                row_idx, codigo, codigo_articulo,
            )
            skipped.append({
                "_row": row_idx,
                "codigo": codigo,
                "codigo_articulo": codigo_articulo,
                "reason": (
                    f"row {row_idx}: FK miss articulo {codigo_articulo!r} "
                    f"(codigo={codigo!r}), skipped"
                ),
            })
            continue

        pre_heuristic_rows.append({
            "articulo_id": articulo_id,
            "codigo": codigo,
            "codigo_articulo": codigo_articulo,
            "cantidad": cantidad_raw,
            "_row": row_idx,
        })

    # Apply tipo heuristic over the FULL list (groups by codigo_articulo).
    # Returns the same list reference with each dict updated to include 'tipo'.
    rows_with_tipo = assign_tipos(pre_heuristic_rows)

    logger.info(
        "extract complete: rows=%d skipped=%d",
        len(rows_with_tipo), len(skipped),
    )

    return rows_with_tipo, skipped


# ---------------------------------------------------------------------------
# load — upsert idempotente por (articulo_id, codigo)
# ---------------------------------------------------------------------------

def load(
    session,
    rows: Iterable[dict],
    *,
    batch_size: int = 1000,
) -> LoadReport:
    """Upsert idempotente de ArticuloCodigo por `(articulo_id, codigo)`.

    Patron mismo que `articulos_proveedores_xls.load`:
      - `existing = {(ac.articulo_id, ac.codigo): ac for ac in
        session.query(ArticuloCodigo).all()}` UNA vez al inicio.
      - Key no en existing -> INSERT (session.add).
      - Key en existing -> UPDATE in-place de `tipo` si difiere.
      - Sin deltas -> SKIP.
      - Flush cada `batch_size` rows (default 1000).

    UPDATE path: solo machaca `tipo` (last-wins). Nota: Change A backfilleo
    `tipo='principal'` para los codigos legacy de `Articulo.codigo_barras`;
    EMPAQUETADOS puede re-clasificar el mismo `(articulo_id, codigo)` con
    distinto tipo segun la heuristica. La rama UPDATE lo refleja
    idempotentemente.

    Insert path: crea `ArticuloCodigo` con `articulo_id`, `codigo`, `tipo`.

    Intra-sheet duplicate `(articulo_id, codigo)`: last-wins. La 2da
    ocurrencia entra por rama UPDATE y sobrescribe `tipo`. Tambien se
    loguea WARN.
    """
    report = LoadReport(entity="empaquetados_xls")
    report.start()

    existing: dict[tuple[int, str], ArticuloCodigo] = {
        (ac.articulo_id, ac.codigo): ac
        for ac in session.query(ArticuloCodigo).all()
    }
    seen_in_run: set[tuple[int, str]] = set()
    pending_flush = 0

    for row in rows:
        report.read += 1

        articulo_id = row["articulo_id"]
        codigo = row["codigo"]
        tipo = row["tipo"]
        row_idx = row.get("_row")
        key = (articulo_id, codigo)
        identifier = f"{articulo_id}/{codigo}"

        # Intra-sheet duplicate detection.
        if key in seen_in_run:
            report.warn(
                identifier,
                f"row {row_idx}: intra-sheet duplicate (articulo_id, codigo) (last-wins)",
            )
        seen_in_run.add(key)

        try:
            current = existing.get(key)
            if current is None:
                # INSERT path.
                ac = ArticuloCodigo(
                    articulo_id=articulo_id,
                    codigo=codigo,
                    tipo=tipo,
                )
                session.add(ac)
                existing[key] = ac
                report.inserted += 1
                pending_flush += 1
            else:
                # UPDATE path (idempotente). Solo `tipo`.
                if current.tipo != tipo:
                    current.tipo = tipo
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
