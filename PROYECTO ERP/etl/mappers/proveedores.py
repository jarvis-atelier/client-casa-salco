"""Mapper PROVEEDO.DBF -> Proveedor."""
from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path

from dbfread import DBF

from app.models import Proveedor

from .common import LoadReport, clean_str, sanitize_text

DBF_NAME = "PROVEEDO.DBF"


def extract(source_dir: Path, encoding: str = "cp1252") -> Iterator[dict]:
    """Lee PROVEEDO.DBF y emite dicts listos para instanciar Proveedor.

    Campos legacy relevantes:
      CODIGO (N,4), DESC (razon social), CUIT, TELEFONO, DOMICILIO,
      LOCALIDAD, PROVINCIA, OBSERVA1 (notas/email). NUIV (cond IVA) se
      conserva como legacy_meta si el modelo lo soportara (por ahora solo activa).
    """
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
        # Filtros: si no hay codigo ni desc, es un registro template vacio -> skip.
        if not codigo and not desc:
            continue
        if codigo is None or codigo == 0:
            # sin codigo no podemos crear unique - saltar
            continue
        # Direccion concatenada para el campo unico direccion del modelo
        domicilio = clean_str(rec.get("domicilio"))
        localidad = clean_str(rec.get("localidad"))
        provincia = clean_str(rec.get("provincia"))
        direccion = ", ".join(p for p in (domicilio, localidad, provincia) if p) or None

        yield {
            "codigo": str(codigo).strip(),
            "razon_social": desc or f"Proveedor {codigo}",
            "cuit": clean_str(rec.get("cuit"), max_len=15),
            "telefono": clean_str(rec.get("telefono"), max_len=50),
            "email": None,  # legacy no tiene campo email dedicado
            "direccion": sanitize_text(direccion, max_len=255),
            "activo": True,
        }


def load(session, rows: Iterable[dict], *, dry_run: bool = False) -> LoadReport:
    report = LoadReport(entity="proveedores")
    report.start()

    # Cache de codigos existentes para decidir insert vs update sin N queries
    existing: dict[str, Proveedor] = {
        p.codigo: p for p in session.query(Proveedor).all()
    }

    for row in rows:
        report.read += 1
        codigo = row["codigo"]
        try:
            current = existing.get(codigo)
            if current is None:
                new = Proveedor(**row)
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
        except Exception as exc:  # pragma: no cover - salvaguarda defensiva
            report.failed += 1
            report.warn(codigo, f"error al cargar: {exc}")

    if not dry_run:
        session.flush()
    report.finish()
    return report
