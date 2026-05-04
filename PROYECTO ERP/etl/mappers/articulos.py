"""Mapper ARTICULO.DBF -> Articulo.

El DBF legacy tiene 196+ columnas (talle/color expandido). Extraemos SOLO
los campos mapeables al modelo nuevo.

Estrategia de FK:
  - rubro_id: ARTICULO.rubro no existe como columna en este schema, pero SI
    el legacy usa `rubro` como FK logico mapeado por codigo numerico. En los
    DBFs disponibles no aparece -> probamos LINEA (ARTICULO.linea) como proxy
    de categoria. Si LINEA no da nada, cae a "sin-rubro".
  - familia_id: derivado del rubro (rubro.familia_id) o "sin-familia".
  - proveedor_principal_id: ARTICULO.proveedor (N,5) -> Proveedor por codigo.
  - marca_id: legacy guarda una letra (C len=1) en MARCA; no hay catalogo
    de marcas real. Por ahora NO mapeamos marca (queda NULL).
"""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from dbfread import DBF

from app.models import Articulo, Familia, Proveedor, Rubro

from .common import (
    LoadReport,
    decimal_or_zero,
    sanitize_text,
    unidad_medida_from_legacy,
)

DBF_NAME = "ARTICULO.DBF"


def _is_empty_record(rec: dict) -> bool:
    """True si es un registro template: sin codigo y sin descripcion util."""
    codigo = rec.get("codigo")
    desc = rec.get("desc")
    desc_clean = desc.strip() if isinstance(desc, str) else ""
    return not codigo and not desc_clean


def extract(source_dir: Path, encoding: str = "cp1252") -> Iterator[dict]:
    """Lee ARTICULO.DBF. NO filtra por FKs (eso lo hace load)."""
    path = source_dir / DBF_NAME
    if not path.exists():
        return
    table = DBF(
        str(path),
        encoding=encoding,
        char_decode_errors="replace",
        ignore_missing_memofile=True,
        lowernames=True,
    )
    for rec in table:
        if _is_empty_record(rec):
            continue
        codigo = rec.get("codigo")
        if codigo is None or codigo == 0:
            # codigo=0 en legacy es el "registro template" tipico
            continue
        desc = sanitize_text(rec.get("desc"), max_len=255) or f"Articulo {codigo}"
        barras_raw = rec.get("barras")
        # Legacy guarda barras como N(15,0). 0 o None -> sin barras.
        if barras_raw in (None, 0, 0.0):
            codigo_barras = None
        else:
            try:
                codigo_barras = str(int(barras_raw))
            except (ValueError, TypeError):
                codigo_barras = sanitize_text(barras_raw, max_len=50)

        costo = decimal_or_zero(rec.get("costo"), places=4)
        venta = decimal_or_zero(rec.get("venta"), places=4)
        iva_porc = decimal_or_zero(rec.get("iva"), places=2)
        # Si IVA es 0 (default legacy no cargado), asumimos 21
        if iva_porc == Decimal("0"):
            iva_porc = Decimal("21")

        unid = rec.get("unid")
        unidad = unidad_medida_from_legacy(unid, desc=desc)

        # Legacy "rubro": no existe como columna en este ARTICULO.DBF concreto,
        # pero en otros DBFs puede estar. getattr defensivo.
        legacy_rubro = rec.get("rubro")
        legacy_linea = rec.get("linea")
        legacy_proveedor = rec.get("proveedor")

        yield {
            "codigo": str(int(codigo)) if isinstance(codigo, (int, float)) else str(codigo).strip(),
            "descripcion": desc,
            "codigo_barras": codigo_barras,
            "_legacy_rubro": int(legacy_rubro) if legacy_rubro else None,
            "_legacy_linea": int(legacy_linea) if legacy_linea else None,
            "_legacy_proveedor": (
                int(legacy_proveedor) if legacy_proveedor else None
            ),
            "unidad_medida": unidad,
            "costo": costo,
            "pvp_base": venta,
            "iva_porc": iva_porc,
            "activo": True,
            "controla_stock": True,
            "controla_vencimiento": False,
        }


def _fallback_rubro(session) -> Rubro | None:
    """Rubro por defecto ('sin-rubro') bajo familia 'sin-familia'."""
    return (
        session.query(Rubro)
        .filter(Rubro.codigo == "sin-rubro")
        .first()
    )


def _fallback_familia(session) -> Familia | None:
    return session.query(Familia).filter(Familia.codigo == "sin-familia").first()


def load(
    session,
    rows: Iterable[dict],
    *,
    dry_run: bool = False,
    rubro_lookup: dict[int, Rubro] | None = None,
) -> LoadReport:
    """Inserta / actualiza articulos. rubro_lookup mapea legacy_rubro_code -> Rubro."""
    report = LoadReport(entity="articulos")
    report.start()

    rubro_lookup = rubro_lookup or {}
    fallback_rubro = _fallback_rubro(session)
    fallback_familia = _fallback_familia(session)

    # Proveedores por codigo legacy (el codigo se mantiene como str numerico)
    proveedores_by_code: dict[str, Proveedor] = {
        p.codigo: p for p in session.query(Proveedor).all()
    }

    existing: dict[str, Articulo] = {
        a.codigo: a for a in session.query(Articulo).all()
    }

    for row in rows:
        report.read += 1
        codigo = row["codigo"]
        try:
            legacy_rubro = row.pop("_legacy_rubro", None)
            _legacy_linea = row.pop("_legacy_linea", None)  # noqa: F841 - no usado aun
            legacy_prov = row.pop("_legacy_proveedor", None)

            # Resolver rubro
            rubro_obj: Rubro | None = None
            if legacy_rubro is not None and legacy_rubro in rubro_lookup:
                rubro_obj = rubro_lookup[legacy_rubro]
            if rubro_obj is None:
                rubro_obj = fallback_rubro
                if legacy_rubro is not None:
                    report.warn(
                        codigo,
                        f"rubro legacy {legacy_rubro} no encontrado -> sin-rubro",
                    )

            # Familia deriva del rubro (o del fallback)
            familia_obj = (
                rubro_obj.familia if rubro_obj and rubro_obj.familia else fallback_familia
            )

            row["rubro"] = rubro_obj
            row["familia"] = familia_obj

            # Resolver proveedor
            proveedor_obj = None
            if legacy_prov is not None:
                proveedor_obj = proveedores_by_code.get(str(legacy_prov))
                if proveedor_obj is None:
                    report.warn(
                        codigo,
                        f"proveedor legacy {legacy_prov} no encontrado -> sin proveedor principal",
                    )
            row["proveedor_principal"] = proveedor_obj

            current = existing.get(codigo)
            if current is None:
                new = Articulo(**row)
                if not dry_run:
                    session.add(new)
                existing[codigo] = new
                report.inserted += 1
            else:
                changed = False
                for key, value in row.items():
                    if key == "codigo":
                        continue
                    old = getattr(current, key)
                    # Evita detectar cambio espurio entre Decimals equivalentes
                    if isinstance(value, Decimal) and isinstance(old, Decimal):
                        if old.compare(value) != Decimal("0"):
                            if not dry_run:
                                setattr(current, key, value)
                            changed = True
                    elif old != value:
                        if not dry_run:
                            setattr(current, key, value)
                        changed = True
                if changed:
                    report.updated += 1
                else:
                    report.skipped += 1
        except Exception as exc:  # pragma: no cover
            report.failed += 1
            report.warn(codigo, f"error al cargar: {exc}")

    if not dry_run:
        session.flush()
    report.finish()
    return report
