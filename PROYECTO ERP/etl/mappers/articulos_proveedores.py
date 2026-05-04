"""Mapper ARTIPROV.DBF -> ArticuloProveedor (relacion M2M con metadata)."""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from dbfread import DBF

from app.models import Articulo, ArticuloProveedor, Proveedor

from .common import LoadReport, clean_str, decimal_or_zero

DBF_NAME = "ARTIPROV.DBF"


def extract(source_dir: Path, encoding: str = "cp1252") -> Iterator[dict]:
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
        codi = clean_str(rec.get("codi"))
        provee = clean_str(rec.get("provee"))
        if not codi or not provee:
            continue
        yield {
            "_articulo_codigo": codi,
            "_proveedor_codigo": provee,
            "codigo_proveedor": clean_str(rec.get("nropro"), max_len=50),
            "costo_proveedor": decimal_or_zero(rec.get("prco"), places=4),
            "ultimo_ingreso": rec.get("feulco"),
        }


def load(session, rows: Iterable[dict], *, dry_run: bool = False) -> LoadReport:
    report = LoadReport(entity="articulos_proveedores")
    report.start()

    articulos_by_code = {a.codigo: a for a in session.query(Articulo).all()}
    proveedores_by_code = {p.codigo: p for p in session.query(Proveedor).all()}

    # Cache existente por (articulo_id, proveedor_id)
    existing: dict[tuple[int, int], ArticuloProveedor] = {
        (ap.articulo_id, ap.proveedor_id): ap
        for ap in session.query(ArticuloProveedor).all()
    }

    for row in rows:
        report.read += 1
        art_code = row.pop("_articulo_codigo")
        prov_code = row.pop("_proveedor_codigo")
        art = articulos_by_code.get(art_code)
        prov = proveedores_by_code.get(prov_code)
        if art is None:
            report.failed += 1
            report.warn(f"{art_code}/{prov_code}", f"articulo '{art_code}' no existe")
            continue
        if prov is None:
            report.failed += 1
            report.warn(f"{art_code}/{prov_code}", f"proveedor '{prov_code}' no existe")
            continue
        key = (art.id, prov.id) if art.id and prov.id else None
        current = existing.get(key) if key else None
        if current is None:
            new = ArticuloProveedor(articulo=art, proveedor=prov, **row)
            if not dry_run:
                session.add(new)
            report.inserted += 1
        else:
            changed = False
            for k, v in row.items():
                if getattr(current, k) != v:
                    if not dry_run:
                        setattr(current, k, v)
                    changed = True
            if changed:
                report.updated += 1
            else:
                report.skipped += 1

    if not dry_run:
        session.flush()
    report.finish()
    return report
