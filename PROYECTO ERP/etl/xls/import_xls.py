"""Importador ETL desde los .xls legacy de Casa Salco hacia la DB nueva.

Uso (dry-run, no escribe a la DB):
    python -m etl.xls.import_xls \\
        --proveedores PATH_FILE_1 \\
        --articulos PATH_FILE_2 \\
        --articulos-proveedores PATH_FILE_1 \\
        --dry-run

Espejo estructural de `etl/import_dbfs.py`. Las mapper bodies (proveedores,
articulos, articulos_proveedores) se llenan en fases posteriores
(B3, B4, B5). Esta version es el SCAFFOLD: parsea flags, hace dry-run,
e imprime que fase HARIA — sin tocar la DB.

Requisitos:
    pip install -e "../backend[import-xls]"
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

import click

# Hace que el paquete `app` (backend) sea importable desde este script.
# Mismo patron que etl/import_dbfs.py:30-31.
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_OK = 0          # all phases committed clean
EXIT_PARTIAL = 1     # some rows skipped/errored, but committed
EXIT_FAILURE = 2     # rolled back / fatal


# ---------------------------------------------------------------------------
# Paths para reports y logs
# ---------------------------------------------------------------------------

XLS_ROOT = Path(__file__).resolve().parent
DEFAULT_REPORT_OUT = XLS_ROOT / "reports"
LOG_FILE = XLS_ROOT / "last-run.log"
REPORT_FILE = XLS_ROOT / "last-report.md"

logger = logging.getLogger("etl.xls")


# ---------------------------------------------------------------------------
# Setup logging — espejo de etl/import_dbfs.py:65-83
# ---------------------------------------------------------------------------

def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
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
# CLI (Click) — surface definida en design Section 8
# ---------------------------------------------------------------------------

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--proveedores",
    type=click.Path(path_type=Path),
    required=True,
    help="Ruta al .xls File 1 (sheet 'proveedor').",
)
@click.option(
    "--articulos",
    type=click.Path(path_type=Path),
    required=True,
    help="Ruta al .xls File 2 (sheet 'Sheet1').",
)
@click.option(
    "--articulos-proveedores",
    type=click.Path(path_type=Path),
    required=True,
    help="Ruta al .xls File 1 (sheet 'RELACION PRODUCTOS PROVEEDOR').",
)
@click.option(
    "--skip-compra-cero/--no-skip-compra-cero",
    default=False,
    show_default=True,
    help="Si esta ON, articulos con COMPRA=0 son saltados. Default OFF.",
)
@click.option(
    "--dry-run/--no-dry-run",
    default=False,
    show_default=True,
    help="No escribe a la DB; solo extrae y reporta. Hace rollback al final.",
)
@click.option(
    "--batch-size",
    type=int,
    default=1000,
    show_default=True,
    help="Cantidad de filas por flush() de la session.",
)
@click.option(
    "--report-out",
    type=click.Path(path_type=Path),
    default=DEFAULT_REPORT_OUT,
    show_default=True,
    help="Directorio para los reports markdown timestamped.",
)
@click.option(
    "--db-url",
    type=str,
    default=None,
    help="URL de conexion a Postgres. Default: env DATABASE_URL.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Log DEBUG en stdout.",
)
def main(
    proveedores: Path,
    articulos: Path,
    articulos_proveedores: Path,
    skip_compra_cero: bool,
    dry_run: bool,
    batch_size: int,
    report_out: Path,
    db_url: str | None,
    verbose: bool,
) -> None:
    """Importa los .xls legacy de Casa Salco (Proveedor, Articulo, ArticuloProveedor)."""
    setup_logging(verbose=verbose)

    resolved_db_url = db_url or os.environ.get("DATABASE_URL")
    ts = time.strftime("%Y-%m-%dT%H:%M:%S")

    click.echo(
        f"[xls-import] start ts={ts} dry_run={dry_run} "
        f"skip_compra_cero={skip_compra_cero} batch_size={batch_size}"
    )
    logger.info(
        "config: proveedores=%s articulos=%s articulos_proveedores=%s "
        "report_out=%s db_url=%s",
        proveedores, articulos, articulos_proveedores, report_out,
        "<env>" if resolved_db_url else "<unset>",
    )
    if db_url:
        # Decision (B3): el contexto DB se construye via app.create_app()
        # (espejo de etl/import_dbfs.py), que lee DATABASE_URL del env. El
        # flag --db-url queda wired pero no se consume hasta que tengamos
        # un caso real para overridearlo. Loguear como TODO para no
        # romper la contract si el usuario lo pasa.
        logger.warning(
            "TODO: --db-url=%s recibido pero no se usa todavia; "
            "create_app() lee DATABASE_URL del env. Ver B3 progress.",
            db_url,
        )

    # Phase: proveedores
    click.echo(f"[xls-import] phase=proveedores file={proveedores}")
    if not dry_run:
        # Imports tardios: dependen de BACKEND_ROOT en sys.path (definido arriba)
        # y de que la session SQLAlchemy este disponible via Flask app context.
        from app import create_app  # noqa: E402
        from app.extensions import db as _db  # noqa: E402

        from etl.xls.mappers import proveedores_xls  # noqa: E402

        flask_app = create_app()
        with flask_app.app_context():
            session = _db.session
            try:
                rows = proveedores_xls.extract(proveedores, sheet_name="proveedor")
                report_prov = proveedores_xls.load(session, rows, batch_size=batch_size)
                session.commit()
                click.echo(
                    f"[xls-import]   inserted={report_prov.inserted} "
                    f"updated={report_prov.updated} "
                    f"skipped={report_prov.skipped} "
                    f"errors={report_prov.failed}"
                )
            except Exception as exc:
                session.rollback()
                logger.exception("proveedores phase failed: %s", exc)
                sys.exit(EXIT_FAILURE)
    else:
        click.echo("[xls-import]   dry-run — proveedores phase skipped")

    # Phase: articulos
    click.echo(f"[xls-import] phase=articulos file={articulos}")
    if not dry_run:
        # Imports tardios (deps en BACKEND_ROOT en sys.path + Flask app context).
        # NOTE: si la fase de proveedores acaba de commitear, los nuevos
        # ids YA estan en la DB; build_fk_caches los lee fresh.
        from app import create_app  # noqa: E402
        from app.extensions import db as _db  # noqa: E402

        from etl.xls.mappers import articulos_xls  # noqa: E402

        flask_app = create_app()
        with flask_app.app_context():
            session = _db.session
            try:
                fk_caches = articulos_xls.build_fk_caches(session)
                rows_art, legacy_catalog, compra_zero = articulos_xls.extract(
                    articulos,
                    sheet_name="Sheet1",
                    fk_caches=fk_caches,
                    skip_compra_cero=skip_compra_cero,
                )
                report_art = articulos_xls.load(
                    session, rows_art, batch_size=batch_size
                )
                session.commit()
                # `legacy_catalog` y `compra_zero` quedan disponibles para B6
                # (Report writer). Por ahora los logueamos como counts y los
                # surface-amos via stdout. B6 los persistira al markdown.
                click.echo(
                    f"[xls-import]   inserted={report_art.inserted} "
                    f"updated={report_art.updated} "
                    f"skipped={report_art.skipped} "
                    f"errors={report_art.failed} "
                    f"compra_zero={len(compra_zero)} "
                    f"legacy_rows={len(legacy_catalog)}"
                )
            except Exception as exc:
                session.rollback()
                logger.exception("articulos phase failed: %s", exc)
                sys.exit(EXIT_FAILURE)
    else:
        click.echo("[xls-import]   dry-run — articulos phase skipped")

    # Phase: articulos_proveedores
    click.echo(f"[xls-import] phase=articulos_proveedores file={articulos_proveedores}")
    # TODO: mapper call (Phase 5)

    # Report
    click.echo("[xls-import] phase=report")
    # TODO: report writer (Phase 6)

    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
