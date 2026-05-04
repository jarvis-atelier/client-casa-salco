"""Mapper CLIENTES.DBF -> Cliente."""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from decimal import Decimal
from pathlib import Path

from dbfread import DBF

from app.models import Cliente, CondicionIvaEnum

from .common import (
    LoadReport,
    NUIV_TO_CONDICION_IVA,
    bool_from_legacy,
    clean_str,
    decimal_or_zero,
    sanitize_text,
)

DBF_NAME = "CLIENTES.DBF"


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
        codigo = rec.get("codigo")
        desc = sanitize_text(rec.get("desc"), max_len=255)
        if not codigo and not desc:
            continue
        if not codigo:
            continue
        nuiv = rec.get("nuiv")
        try:
            nuiv_int = int(nuiv) if nuiv is not None else 1
        except (TypeError, ValueError):
            nuiv_int = 1
        condicion = NUIV_TO_CONDICION_IVA.get(nuiv_int, CondicionIvaEnum.consumidor_final)

        domicilio = clean_str(rec.get("domicilio"))
        localidad = clean_str(rec.get("localidad"))
        provincia = clean_str(rec.get("provincia"))
        direccion = ", ".join(p for p in (domicilio, localidad, provincia) if p) or None

        # habilitar=1 en legacy significa activo
        activo = bool_from_legacy(rec.get("habilitar"))
        # Si no esta explicitamente desactivado, lo marcamos activo
        if rec.get("habilitar") is None:
            activo = True

        saldo: Decimal = decimal_or_zero(rec.get("sald"), places=2)
        limite: Decimal = decimal_or_zero(rec.get("limite"), places=2)

        yield {
            "codigo": str(codigo).strip(),
            "razon_social": desc or f"Cliente {codigo}",
            "cuit": clean_str(rec.get("cuit"), max_len=15),
            "condicion_iva": condicion,
            "telefono": clean_str(rec.get("telefono"), max_len=50),
            "email": clean_str(rec.get("mail"), max_len=200),
            "direccion": sanitize_text(direccion, max_len=255),
            "cuenta_corriente": limite > 0,
            "limite_cuenta_corriente": limite,
            "saldo": saldo,
            "activo": activo,
        }


def load(session, rows: Iterable[dict], *, dry_run: bool = False) -> LoadReport:
    report = LoadReport(entity="clientes")
    report.start()

    existing: dict[str, Cliente] = {c.codigo: c for c in session.query(Cliente).all()}

    for row in rows:
        report.read += 1
        codigo = row["codigo"]
        try:
            current = existing.get(codigo)
            if current is None:
                new = Cliente(**row)
                if not dry_run:
                    session.add(new)
                existing[codigo] = new
                report.inserted += 1
            else:
                changed = False
                for key, value in row.items():
                    if key == "codigo":
                        continue
                    if getattr(current, key) != value:
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
