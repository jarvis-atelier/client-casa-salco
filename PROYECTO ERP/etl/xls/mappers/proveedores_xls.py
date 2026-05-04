"""Mapper File 1 (h00ugz.xls) sheet 'proveedor' -> Proveedor.

Espejo del patron `etl/mappers/proveedores.py` (DBF) pero adaptado al
shape del .xls legacy: el sheet `proveedor` tiene 7 columnas con headers
mojibake-cp1252 que `read_sheet` ya decodifica antes de yieldear:

    Codigo | Nombre | Telefono | Email | Clasificacion |
    Descripcion clasificacion proveedor | CUIT

Solo las columnas C{o}digo, Nombre, Tel{e}fono, Email, CUIT mapean al
modelo `Proveedor`. Clasificaci{o}n y Descripci{o}n clasificaci{o}n
proveedor se preservan en `_legacy` para warning logs (NO se persisten,
no hay campo en el modelo).
"""
from __future__ import annotations

import logging
import re
from collections.abc import Iterable, Iterator
from pathlib import Path

from app.models import Proveedor

from etl.mappers.common import LoadReport, clean_str, sanitize_text
from etl.xls.mappers.common_xls import read_sheet

logger = logging.getLogger("etl.xls.proveedores")

# Header keys reales (post `decode_xls_str`) en el sheet 'proveedor'.
COL_CODIGO = "Código"
COL_NOMBRE = "Nombre"
COL_TELEFONO = "Teléfono"
COL_EMAIL = "Email"
COL_CLASIFICACION = "Clasificación"
COL_DESC_CLASIF = "Descripción clasificación proveedor"
COL_CUIT = "CUIT"

# Junk patterns. La descripcion '0000' / 'test' / etc. son rows muertas
# del legacy. Match case-insensitive, anclado al inicio.
_JUNK_NOMBRE_RE = re.compile(r"^(test|prueba|xxx)", re.IGNORECASE)


def _normalize_cuit(value) -> str | None:
    """Devuelve solo digitos del CUIT, o None si queda vacio.

    El xls trae CUIT con guiones (`20-34791485-2`); `Proveedor.cuit` es
    `String(15)` y la convencion del sistema (DBF importer) lo guarda
    como digitos puros.
    """
    s = clean_str(value)
    if s is None:
        return None
    digits = re.sub(r"\D", "", s)
    return digits or None


def extract(workbook_path: Path | str, sheet_name: str = "proveedor") -> Iterator[dict]:
    """Itera el sheet 'proveedor' del File 1 y yieldea dicts normalizados.

    Aplica el junk filter (design Section 6):
      - skip si codigo IS None / '' / '0000'
      - skip si codigo == nombre (rows muertas tipo '0000|0000|...')
      - skip si nombre matchea ^test|^prueba|^xxx (case-insensitive)

    Cada skip se loggea con el numero de fila + razon.

    Yieldea dicts con keys:
      codigo, razon_social, telefono, email, cuit, _legacy

    `_legacy` contiene `clasificacion` y `desc_clasificacion` para que el
    caller pueda surface-arlos en el report markdown como warnings, sin
    persistirlos al modelo.
    """
    path_str = str(workbook_path)
    for row_idx, row in enumerate(read_sheet(path_str, sheet_name), start=2):
        # row_idx empieza en 2 porque la fila 0 es header y read_sheet la consume;
        # la primera data row corresponde a fila excel #2 (1-indexed).

        codigo_raw = row.get(COL_CODIGO)
        nombre_raw = row.get(COL_NOMBRE)

        codigo = clean_str(codigo_raw)
        nombre = sanitize_text(nombre_raw, max_len=255)

        # Junk: codigo vacio / '0000' / None
        if codigo is None or codigo == "" or codigo == "0000":
            logger.info(
                "row=%d skip codigo=%r reason='codigo vacio o 0000'",
                row_idx, codigo_raw,
            )
            continue

        # Junk: codigo == nombre (rows '0000|0000|0000|...')
        if nombre is not None and codigo == nombre:
            logger.info(
                "row=%d skip codigo=%r reason='codigo == nombre'",
                row_idx, codigo,
            )
            continue

        # Junk: nombre matchea patrones de test/prueba
        if nombre and _JUNK_NOMBRE_RE.match(nombre):
            logger.info(
                "row=%d skip codigo=%r nombre=%r reason='nombre matches test/prueba/xxx'",
                row_idx, codigo, nombre,
            )
            continue

        clasificacion = clean_str(row.get(COL_CLASIFICACION))
        desc_clasif = clean_str(row.get(COL_DESC_CLASIF))

        yield {
            "codigo": codigo,
            "razon_social": nombre or f"Proveedor {codigo}",
            "telefono": clean_str(row.get(COL_TELEFONO), max_len=50),
            "email": clean_str(row.get(COL_EMAIL), max_len=200),
            "cuit": _normalize_cuit(row.get(COL_CUIT)),
            "_legacy": {
                "clasificacion": clasificacion,
                "desc_clasificacion": desc_clasif,
                "row": row_idx,
            },
        }


def load(session, rows: Iterable[dict], *, batch_size: int = 1000) -> LoadReport:
    """Upsert idempotente de Proveedor por `codigo` (natural key).

    Patron mismo que `etl/mappers/proveedores.py`:
      - Se construye `existing = {p.codigo: p for p in session.query(Proveedor).all()}`
        UNA sola vez al inicio. Todo el loop trabaja contra ese dict para
        evitar N queries.
      - Si `codigo` no existe -> INSERT (session.add).
      - Si `codigo` existe -> UPDATE in-place de `razon_social`, `cuit`,
        `telefono`, `email`. Preserva `id`, `activo`, `direccion` y otros
        campos no provistos por el .xls.
      - Si los campos coinciden -> SKIP (no-op).
      - Flush cada `batch_size` rows (default 1000).

    Intra-sheet duplicate codigo: last-wins por design. La segunda
    ocurrencia entra por la rama UPDATE (porque el primer add ya esta en
    `existing`) y sobrescribe los campos. Tambien se loguea WARN.
    """
    report = LoadReport(entity="proveedores_xls")
    report.start()

    existing: dict[str, Proveedor] = {
        p.codigo: p for p in session.query(Proveedor).all()
    }
    pending_flush = 0

    for row in rows:
        report.read += 1
        codigo = row["codigo"]
        legacy = row.pop("_legacy", None)

        # Surface clasificacion legacy como warning (no persistido).
        if legacy and (legacy.get("clasificacion") or legacy.get("desc_clasificacion")):
            report.warn(
                codigo,
                f"row {legacy.get('row')}: clasificacion legacy "
                f"clasif={legacy.get('clasificacion')!r} "
                f"desc={legacy.get('desc_clasificacion')!r} (no persistida)",
            )

        try:
            current = existing.get(codigo)
            if current is None:
                # INSERT path
                proveedor = Proveedor(
                    codigo=codigo,
                    razon_social=row["razon_social"],
                    cuit=row.get("cuit"),
                    telefono=row.get("telefono"),
                    email=row.get("email"),
                    activo=True,
                )
                session.add(proveedor)
                existing[codigo] = proveedor
                report.inserted += 1
                pending_flush += 1
            else:
                # UPDATE path (idempotente). Si la segunda ocurrencia
                # intra-sheet coincide con la primera, cae en SKIP.
                changed = False
                if current.razon_social != row["razon_social"]:
                    current.razon_social = row["razon_social"]
                    changed = True
                if current.cuit != row.get("cuit"):
                    current.cuit = row.get("cuit")
                    changed = True
                if current.telefono != row.get("telefono"):
                    current.telefono = row.get("telefono")
                    changed = True
                if current.email != row.get("email"):
                    current.email = row.get("email")
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
