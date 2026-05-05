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
from datetime import datetime, timezone
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
    "--empaquetados",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=None,
    help=(
        "Ruta al .xls File 1 (sheet 'EMPAQUETADOS DE PRODUCTOS'). Opcional — "
        "si se omite, la fase EMPAQUETADOS se saltea y queda listada en "
        "'Sheets skipped'."
    ),
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
    empaquetados: Path | None,
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
    # Capture monotonic start + UTC ISO timestamp for the report header.
    # `run_started_monotonic` is for accurate duration math; `run_started_at`
    # is the human-readable ISO string consumed by the report.
    run_started_monotonic = time.monotonic()
    run_started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Accumulators consumed by the Phase 6 Report writer.
    report_prov = None
    report_art = None
    report_ap = None
    report_emp = None  # Phase 7 (B5): empaquetados LoadReport
    legacy_acc: list = []
    compra_zero_acc: list = []
    # Phase 7 (B5): tipo distribution + cantidad_por_pack distribution.
    # Populated only when the empaquetados phase actually runs (flag set + not dry-run).
    empaquetados_counts_by_tipo: dict[str, int] | None = None
    cantidad_por_pack_distribution: list[tuple] | None = None

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
                # Surface to outer-scope accumulators consumed by B6 Report.
                legacy_acc = legacy_catalog
                compra_zero_acc = compra_zero
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
    if not dry_run:
        # Imports tardios (deps en BACKEND_ROOT en sys.path + Flask app context).
        # NOTE: si la fase de articulos acaba de commitear, los nuevos articulos
        # ya estan en la DB y `build_fk_caches` los lee fresh.
        from app import create_app  # noqa: E402
        from app.extensions import db as _db  # noqa: E402

        from etl.xls.mappers import articulos_proveedores_xls  # noqa: E402

        flask_app = create_app()
        with flask_app.app_context():
            session = _db.session
            try:
                fk_caches_ap = articulos_proveedores_xls.build_fk_caches(session)
                rows_ap = articulos_proveedores_xls.extract(
                    articulos_proveedores,
                    sheet_name="RELACION PRODUCTOS PROVEEDOR",
                    fk_caches=fk_caches_ap,
                )
                report_ap = articulos_proveedores_xls.load(
                    session, rows_ap, batch_size=batch_size
                )
                session.commit()
                click.echo(
                    f"[xls-import]   inserted={report_ap.inserted} "
                    f"updated={report_ap.updated} "
                    f"skipped={report_ap.skipped} "
                    f"errors={report_ap.failed}"
                )
            except Exception as exc:
                session.rollback()
                logger.exception("articulos_proveedores phase failed: %s", exc)
                sys.exit(EXIT_FAILURE)
    else:
        click.echo("[xls-import]   dry-run — articulos_proveedores phase skipped")

    # Phase: empaquetados (B5 — Phase 7) — OPTIONAL
    # Only runs if --empaquetados PATH was provided AND not dry_run. Otherwise
    # echoes a skip line and the Report falls back to listing EMPAQUETADOS in
    # `## Sheets skipped` (default behavior).
    click.echo(
        f"[xls-import] phase=empaquetados file={empaquetados}"
        if empaquetados is not None
        else "[xls-import] phase=empaquetados — skipped (no --empaquetados flag)"
    )
    if empaquetados is not None and not dry_run:
        # Imports tardios (deps en BACKEND_ROOT en sys.path + Flask app context).
        # NOTE: corre DESPUES de articulos_proveedores → la FK a Articulo ya esta
        # commiteada y `build_fk_caches` la lee fresh.
        from app import create_app  # noqa: E402
        from app.extensions import db as _db  # noqa: E402

        from etl.xls.mappers import empaquetados_xls  # noqa: E402

        flask_app = create_app()
        with flask_app.app_context():
            session = _db.session
            try:
                fk_caches_emp = empaquetados_xls.build_fk_caches(session)
                rows_emp, _skipped_emp = empaquetados_xls.extract(
                    empaquetados,
                    sheet_name="EMPAQUETADOS DE PRODUCTOS",
                    fk_caches=fk_caches_emp,
                )
                report_emp = empaquetados_xls.load(
                    session, rows_emp, batch_size=batch_size
                )
                session.commit()
                click.echo(
                    f"[xls-import]   inserted={report_emp.inserted} "
                    f"updated={report_emp.updated} "
                    f"skipped={report_emp.skipped} "
                    f"errors={report_emp.failed}"
                )

                # Build report-ready distributions (post-commit DB queries).
                # Counts by tipo: query articulo_codigos grouped by enum value.
                # Distribution: top-20 cantidad_por_pack values across articulo_proveedores.
                from app.models.articulo import ArticuloProveedor  # noqa: E402
                from app.models.articulo_codigo import (  # noqa: E402
                    ArticuloCodigo,
                    TipoCodigoArticuloEnum,
                )
                from sqlalchemy import func  # noqa: E402

                empaquetados_counts_by_tipo = {
                    t.value: session.query(ArticuloCodigo)
                    .filter_by(tipo=t)
                    .count()
                    for t in TipoCodigoArticuloEnum
                }
                cantidad_por_pack_distribution = (
                    session.query(
                        ArticuloProveedor.cantidad_por_pack,
                        func.count().label("n"),
                    )
                    .group_by(ArticuloProveedor.cantidad_por_pack)
                    .order_by(func.count().desc())
                    .limit(20)
                    .all()
                )
            except Exception as exc:
                session.rollback()
                logger.exception("empaquetados phase failed: %s", exc)
                sys.exit(EXIT_FAILURE)
    elif empaquetados is None:
        # Already echoed the skip line above; nothing else to do.
        pass
    else:
        click.echo("[xls-import]   dry-run — empaquetados phase skipped")

    # Phase: report (B6 — Phase 6)
    click.echo("[xls-import] phase=report")
    if not dry_run:
        from etl.xls.report import Report, write_report  # noqa: E402

        # Determine exit status from collected counts.
        # `success` = todos los reports presentes y failed=0 en cada uno.
        # `partial` = hay failed>0 en alguno (rows skipped por FK miss, etc.)
        # `failure` = uno de los reports nunca se construyo (fase abortada).
        load_reports = {
            "Proveedor": report_prov,
            "Articulo": report_art,
            "ArticuloProveedor": report_ap,
        }
        if any(r is None for r in load_reports.values()):
            exit_status = "failure"
        elif any(r.failed > 0 for r in load_reports.values()):
            exit_status = "partial"
        else:
            exit_status = "success"

        # `LoadReport` instances may be None if a phase aborted earlier; we
        # surface them as zero-row entries via the Report's defensive fallback.
        # B5 — Phase 7: when --empaquetados ran successfully, override the
        # default `sheets_skipped` (which lists EMPAQUETADOS) to empty so the
        # report no longer reports it as deferred.
        report_kwargs: dict = {
            "source_proveedores": str(proveedores),
            "source_articulos": str(articulos),
            "source_articulos_proveedores": str(articulos_proveedores),
            "timestamp": run_started_at,
            "duration_seconds": time.monotonic() - run_started_monotonic,
            "exit_status": exit_status,
            "load_reports": {k: v for k, v in load_reports.items() if v is not None},
            "legacy_catalog": legacy_acc,
            "compra_zero": compra_zero_acc,
            "empaquetados_counts_by_tipo": empaquetados_counts_by_tipo,
            "cantidad_por_pack_distribution": cantidad_por_pack_distribution,
        }
        if empaquetados is not None:
            # Empaquetados ran (not dry-run path) → drop default skip entry.
            report_kwargs["sheets_skipped"] = []
        report = Report(**report_kwargs)
        timestamped_path, last_path = write_report(report, Path(report_out))
        click.echo(f"[xls-import]   report={timestamped_path}")
        click.echo(f"[xls-import]   last={last_path}")

        # Map exit_status -> CLI exit code.
        if exit_status == "failure":
            sys.exit(EXIT_FAILURE)
        if exit_status == "partial":
            sys.exit(EXIT_PARTIAL)
        sys.exit(EXIT_OK)
    else:
        click.echo("[xls-import]   dry-run — report phase skipped")
        sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
