"""Importador ETL desde los DBFs del sistema viejo hacia la DB nueva.

Uso:
    # Dry-run (no escribe, solo reporta)
    python import_dbfs.py --source ../../viejo/DBF --dry-run

    # Corrida real
    python import_dbfs.py --source ../../viejo/DBF

    # Seleccionar dominios
    python import_dbfs.py --source ../../viejo/DBF --tables proveedores clientes

    # Wipe + reimport
    python import_dbfs.py --source ../../viejo/DBF --truncate

Requisitos:
    pip install -e "../backend[etl]"
"""
from __future__ import annotations

import logging
import sys
import time
from pathlib import Path

import click

# Hace que el paquete `app` (backend) sea importable desde este script.
BACKEND_ROOT = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

from mappers import LoadReport  # noqa: E402
from mappers import articulos as m_articulos  # noqa: E402
from mappers import articulos_proveedores as m_artprov  # noqa: E402
from mappers import clientes as m_clientes  # noqa: E402
from mappers import familias_rubros as m_famrub  # noqa: E402
from mappers import proveedores as m_proveedores  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SOURCE = REPO_ROOT / "viejo" / "DBF"
LOG_FILE = Path(__file__).resolve().parent / "last-run.log"
REPORT_FILE = Path(__file__).resolve().parent / "last-report.md"

REQUIRED_DBFS = ["ARTICULO.DBF", "CLIENTES.DBF", "PROVEEDO.DBF"]
ALL_TABLES = [
    "proveedores",
    "familias",
    "rubros",
    "clientes",
    "articulos",
    "articulos_proveedores",
]

logger = logging.getLogger("etl")


# ---------------------------------------------------------------------------
# Setup logging
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    # Reset handlers to re-run cleanly on repeated invocations (useful for tests)
    for h in logger.handlers[:]:
        logger.removeHandler(h)
    logger.setLevel(level)
    logger.propagate = False

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter(fmt))
    logger.addHandler(ch)

    fh = logging.FileHandler(LOG_FILE, mode="w", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(fmt))
    logger.addHandler(fh)


# ---------------------------------------------------------------------------
# Validacion pre-run
# ---------------------------------------------------------------------------

def validate_source(source: Path) -> None:
    if not source.exists():
        raise click.ClickException(f"Source no existe: {source}")
    missing = [f for f in REQUIRED_DBFS if not (source / f).exists()]
    if missing:
        raise click.ClickException(
            f"DBFs requeridos faltantes en {source}: {', '.join(missing)}"
        )
    logger.info("Source OK: %s", source)


def validate_schema() -> None:
    """Verifica que las tablas destino existen. Si no, sugiere flask db upgrade."""
    from sqlalchemy import inspect
    inspector = inspect(db.engine)
    required_tables = {"articulos", "clientes", "proveedores", "familias", "rubros"}
    existing = set(inspector.get_table_names())
    missing = required_tables - existing
    if missing:
        raise click.ClickException(
            "Faltan tablas destino: "
            + ", ".join(sorted(missing))
            + "\nEjecuta: cd backend && flask db upgrade"
        )


# ---------------------------------------------------------------------------
# Operaciones destructivas
# ---------------------------------------------------------------------------

def truncate_all(session) -> None:
    """Borra datos importables en orden FK-safe."""
    from app.models import (
        Articulo,
        ArticuloProveedor,
        Cliente,
        Familia,
        PrecioHistorico,
        PrecioSucursal,
        Proveedor,
        Rubro,
        Subrubro,
    )
    logger.warning("TRUNCATE: borrando datos importables")
    # Orden: hojas primero
    for model in (
        PrecioHistorico,
        PrecioSucursal,
        ArticuloProveedor,
        Articulo,
        Subrubro,
        Rubro,
        Familia,
        Cliente,
        Proveedor,
    ):
        session.query(model).delete()
    session.flush()


# ---------------------------------------------------------------------------
# Corrida por fases
# ---------------------------------------------------------------------------

def run_import(
    source: Path,
    encoding: str,
    tables: list[str],
    dry_run: bool,
    truncate: bool,
) -> list[LoadReport]:
    reports: list[LoadReport] = []
    session = db.session

    if truncate:
        truncate_all(session)

    # --- FASE 1: Proveedores ---------------------------------------------------
    if "proveedores" in tables:
        logger.info("--- FASE proveedores ---")
        rows = list(m_proveedores.extract(source, encoding=encoding))
        r = m_proveedores.load(session, rows, dry_run=dry_run)
        logger.info(
            "proveedores: read=%d inserted=%d updated=%d skipped=%d failed=%d",
            r.read, r.inserted, r.updated, r.skipped, r.failed,
        )
        reports.append(r)

    # --- FASE 2: Familias + Rubros (jerarquia) --------------------------------
    plan_obj = None
    if "familias" in tables or "rubros" in tables or "articulos" in tables:
        logger.info("--- FASE familias/rubros ---")
        plan_obj = m_famrub.plan(source, encoding=encoding)
        rep_f, rep_r = m_famrub.load(session, plan_obj, dry_run=dry_run)
        logger.info(
            "familias: read=%d inserted=%d updated=%d",
            rep_f.read, rep_f.inserted, rep_f.updated,
        )
        logger.info(
            "rubros: read=%d inserted=%d updated=%d",
            rep_r.read, rep_r.inserted, rep_r.updated,
        )
        reports.append(rep_f)
        reports.append(rep_r)

    # --- FASE 3: Clientes -----------------------------------------------------
    if "clientes" in tables:
        logger.info("--- FASE clientes ---")
        rows = list(m_clientes.extract(source, encoding=encoding))
        r = m_clientes.load(session, rows, dry_run=dry_run)
        logger.info(
            "clientes: read=%d inserted=%d updated=%d skipped=%d failed=%d",
            r.read, r.inserted, r.updated, r.skipped, r.failed,
        )
        reports.append(r)

    # --- FASE 4: Articulos ----------------------------------------------------
    if "articulos" in tables:
        logger.info("--- FASE articulos ---")
        # Necesitamos lookup de rubros (legacy_code -> Rubro) usando plan
        if plan_obj is None:
            plan_obj = m_famrub.plan(source, encoding=encoding)
            m_famrub.load(session, plan_obj, dry_run=dry_run)
        rubro_lookup = m_famrub.build_rubro_lookup(session, plan_obj) if not dry_run else {}
        rows = list(m_articulos.extract(source, encoding=encoding))
        r = m_articulos.load(session, rows, dry_run=dry_run, rubro_lookup=rubro_lookup)
        logger.info(
            "articulos: read=%d inserted=%d updated=%d skipped=%d failed=%d",
            r.read, r.inserted, r.updated, r.skipped, r.failed,
        )
        reports.append(r)

    # --- FASE 5: Articulos_Proveedores ---------------------------------------
    if "articulos_proveedores" in tables:
        logger.info("--- FASE articulos_proveedores ---")
        rows = list(m_artprov.extract(source, encoding=encoding))
        r = m_artprov.load(session, rows, dry_run=dry_run)
        logger.info(
            "articulos_proveedores: read=%d inserted=%d updated=%d failed=%d",
            r.read, r.inserted, r.updated, r.failed,
        )
        reports.append(r)

    # --- Commit final ---------------------------------------------------------
    if dry_run:
        logger.info("DRY-RUN: rollback")
        session.rollback()
    else:
        logger.info("Commit final")
        session.commit()

    return reports


# ---------------------------------------------------------------------------
# Reporte markdown
# ---------------------------------------------------------------------------

def write_report(reports: list[LoadReport], *, encoding: str, dry_run: bool) -> None:
    lines = []
    lines.append(f"# ETL Report - {time.strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append(f"Modo: **{'DRY-RUN' if dry_run else 'WRITE'}**  encoding: `{encoding}`")
    lines.append("")
    lines.append("## Resumen")
    lines.append("")
    lines.append("| Entidad | Leidos | Insertados | Actualizados | Saltados | Errores | Tiempo (s) |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|")
    total_warn = 0
    for r in reports:
        lines.append(
            f"| {r.entity} | {r.read} | {r.inserted} | {r.updated} | "
            f"{r.skipped} | {r.failed} | {r.elapsed_s:.2f} |"
        )
        total_warn += len(r.warnings)

    if total_warn:
        lines.append("")
        lines.append("## Warnings / filas con problemas")
        lines.append("")
        for r in reports:
            if not r.warnings:
                continue
            lines.append(f"### {r.entity}")
            for w in r.warnings[:200]:
                lines.append(f"- {w}")
            if len(r.warnings) > 200:
                lines.append(f"- ...y {len(r.warnings) - 200} mas (ver last-run.log)")
            lines.append("")

    REPORT_FILE.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Reporte escrito: %s", REPORT_FILE)


def print_summary(reports: list[LoadReport]) -> None:
    # Tabla ASCII simple para el stdout
    headers = ("Entidad", "Leidos", "Insert", "Update", "Skip", "Fail", "T(s)")
    rows = [r.as_summary_row() for r in reports]
    widths = [max(len(str(h)), *(len(str(row[i])) for row in rows)) for i, h in enumerate(headers)]

    def fmt_row(row):
        return "  ".join(str(row[i]).rjust(widths[i]) for i in range(len(headers)))

    click.echo("")
    click.echo(fmt_row(headers))
    click.echo("  ".join("-" * w for w in widths))
    for row in rows:
        click.echo(fmt_row(row))
    click.echo("")


# ---------------------------------------------------------------------------
# CLI (click)
# ---------------------------------------------------------------------------

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--source",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
    default=DEFAULT_SOURCE,
    show_default=True,
    help="Carpeta con los *.DBF del sistema viejo.",
)
@click.option(
    "--encoding",
    type=click.Choice(["cp1252", "cp850", "latin1", "utf-8"]),
    default="cp1252",
    show_default=True,
    help="Encoding de los DBFs. cp1252 es el default; cp850 para DOS viejo.",
)
@click.option(
    "--tables",
    type=click.Choice(ALL_TABLES + ["todos"]),
    multiple=True,
    default=("todos",),
    show_default=True,
    help="Dominios a importar. Por defecto, todos.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="No escribe en la DB; solo extrae y reporta. Hace rollback al final.",
)
@click.option(
    "--truncate",
    is_flag=True,
    help="PELIGROSO: wipe las tablas destino antes de importar.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Log DEBUG en stdout.",
)
def main(
    source: Path,
    encoding: str,
    tables: tuple[str, ...],
    dry_run: bool,
    truncate: bool,
    verbose: bool,
) -> None:
    """Importa datos desde los DBFs del sistema viejo."""
    setup_logging(verbose=verbose)

    if "todos" in tables:
        selected = list(ALL_TABLES)
    else:
        selected = list(tables)

    logger.info("=" * 60)
    logger.info("ETL start")
    logger.info("source=%s encoding=%s tables=%s dry_run=%s truncate=%s",
                source, encoding, selected, dry_run, truncate)
    logger.info("=" * 60)

    validate_source(source)

    app = create_app()
    with app.app_context():
        validate_schema()

        if truncate and not dry_run:
            click.confirm(
                "--truncate borra TODOS los datos importables. Continuar?",
                abort=True,
            )

        try:
            reports = run_import(
                source=source,
                encoding=encoding,
                tables=selected,
                dry_run=dry_run,
                truncate=truncate,
            )
        except Exception as exc:
            db.session.rollback()
            logger.exception("ETL fallo: %s", exc)
            raise click.ClickException(str(exc)) from exc

    write_report(reports, encoding=encoding, dry_run=dry_run)
    print_summary(reports)

    total_failed = sum(r.failed for r in reports)
    if total_failed:
        click.secho(f"Terminado con {total_failed} errores. Ver {LOG_FILE}", fg="yellow")
        sys.exit(1)
    click.secho("ETL OK", fg="green")


if __name__ == "__main__":
    main()
