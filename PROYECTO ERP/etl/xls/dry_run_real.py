"""One-shot diagnostic: dry-run the .xls import pipeline against real data.

Phase 10.1 + 10.2 (B9) of `sdd/importacion-xls-legacy`. NOT production code.

This script exercises the `extract()` pipeline of each mapper without writing
to the DB (no `session.add`, no `session.commit`). Read-only DB queries are
used to build FK caches. It then aggregates the would-be `Report` and prints
counts + timing + memory profile.

To make `articulos_proveedores` extract counts realistic (the DB only has
~1500 articulos seeded; the .xls master has 34843), we synthesize the
articulo cache from the actual extract output of File 2's Sheet1 (using
synthetic IDs starting at id_offset = max DB id + 1) BEFORE calling
articulos_proveedores.extract. This simulates the post-import state of the
articulos table without writing to the DB.

Usage:
    python -m etl.xls.dry_run_real \\
        --proveedores "D:\\repo\\00-omar\\CASA SALCO\\3EB052EF592E1D591FBB8C-h00ugz.xls" \\
        --articulos   "D:\\repo\\00-omar\\CASA SALCO\\3EB07DF9C6673E43F507BE-615s0b.xls" \\
        --articulos-proveedores "D:\\repo\\00-omar\\CASA SALCO\\3EB052EF592E1D591FBB8C-h00ugz.xls"

Output:
    etl/xls/reports/dry-run-real-{ISO-ts}.md
"""
from __future__ import annotations

import logging
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

import click

# Hace que el paquete `app` (backend) sea importable. Mismo patron que
# import_xls.py.
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

XLS_ROOT = Path(__file__).resolve().parent
DEFAULT_REPORT_OUT = XLS_ROOT / "reports"

logger = logging.getLogger("etl.xls.dry_run_real")


# ---------------------------------------------------------------------------
# psutil is optional — we fall back to tracemalloc only if it's missing.
# ---------------------------------------------------------------------------

def _rss_mb() -> float | None:
    try:
        import psutil  # type: ignore
    except ImportError:
        return None
    proc = psutil.Process()
    return proc.memory_info().rss / (1024 * 1024)


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

TRUNCATE = 20


def _truncate_lines(items: list[str], limit: int = TRUNCATE) -> list[str]:
    if len(items) <= limit:
        return items
    return items[:limit] + [f"... and {len(items) - limit} more"]


def _render_report(
    *,
    ts_iso: str,
    sources: dict[str, str],
    counts: dict[str, dict[str, int]],
    distinct: dict[str, int],
    fk_null_articulos: list[tuple[str, str, str]],  # (codigo, descripcion, raw_proveedor)
    compra_zero: list[tuple[str, str]],
    profile: dict[str, float],
    profile_pass: dict[str, bool],
    targets: dict[str, float],
) -> str:
    lines: list[str] = []
    lines.append(f"# XLS Dry Run — Real Data — {ts_iso}")
    lines.append("")
    lines.append(f"- Source proveedores: {sources['proveedores']}")
    lines.append(f"- Source articulos: {sources['articulos']}")
    lines.append(f"- Source articulos-proveedores: {sources['articulos_proveedores']}")
    lines.append("")
    lines.append("## Counts (extract pipeline)")
    lines.append("")
    lines.append("| Entity | Raw | Junk filtered | FK unresolved | Would import |")
    lines.append("|---|---|---|---|---|")
    for ent in ("Proveedor", "Articulo", "ArticuloProveedor"):
        c = counts[ent]
        fk = c.get("fk_unresolved", "n/a")
        lines.append(
            f"| {ent} | {c['raw']} | {c['junk']} | {fk} | {c['would_import']} |"
        )
    lines.append("")
    lines.append("## Distinct catalog values seen")
    lines.append("")
    lines.append(f"- Distinct rubros: {distinct['rubros']}")
    lines.append(f"- Distinct grupos (familias): {distinct['grupos']}")
    lines.append(f"- Distinct marcas: {distinct['marcas']}")
    lines.append(f"- Distinct grupdesc: {distinct['grupdesc']}")
    lines.append(f"- Distinct categorias: {distinct['categorias']}")
    lines.append("")
    lines.append(f"## FK NULL articulos (proveedor codigo not in DB) — total: {len(fk_null_articulos)}")
    lines.append("")
    if not fk_null_articulos:
        lines.append("(none)")
    else:
        rendered = [
            f'- {codigo} — {descripcion} (proveedor codigo "{raw_prov}" not found)'
            for codigo, descripcion, raw_prov in fk_null_articulos
        ]
        lines.extend(_truncate_lines(rendered))
    lines.append("")
    lines.append(f"## Compra=0 articulos — total: {len(compra_zero)}")
    lines.append("")
    if not compra_zero:
        lines.append("(none)")
    else:
        rendered = [f"- {codigo} — {desc}" for codigo, desc in compra_zero]
        lines.extend(_truncate_lines(rendered))
    lines.append("")
    lines.append("## Profile")
    lines.append("")
    lines.append(f"- Wall time: {profile['wall_seconds']:.2f} s")
    lines.append(f"- Peak memory (tracemalloc): {profile['peak_mb_tracemalloc']:.2f} MB")
    if profile.get("rss_mb") is not None:
        lines.append(f"- RSS memory (psutil): {profile['rss_mb']:.2f} MB")
    else:
        lines.append("- RSS memory (psutil): n/a (psutil not installed)")
    lines.append(f"- Target wall time: < {targets['wall_seconds']:.0f}s "
                 f"-> {'PASS' if profile_pass['wall'] else 'FAIL'}")
    lines.append(f"- Target peak memory: < {targets['peak_mb']:.0f} MB "
                 f"-> {'PASS' if profile_pass['memory'] else 'FAIL'}")
    lines.append("")
    lines.append("### Per-phase wall time")
    lines.append("")
    for label, key in (
        ("proveedores extract", "phase_proveedores_s"),
        ("articulos extract", "phase_articulos_s"),
        ("articulos_proveedores extract", "phase_ap_s"),
        ("FK cache build", "phase_fk_caches_s"),
    ):
        if key in profile:
            lines.append(f"- {label}: {profile[key]:.2f} s")
    lines.append("")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.option(
    "--proveedores",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="Ruta al .xls File 1 (sheet 'proveedor').",
)
@click.option(
    "--articulos",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="Ruta al .xls File 2 (sheet 'Sheet1').",
)
@click.option(
    "--articulos-proveedores",
    type=click.Path(path_type=Path, exists=True),
    required=True,
    help="Ruta al .xls File 1 (sheet 'RELACION PRODUCTOS PROVEEDOR').",
)
@click.option(
    "--report-out",
    type=click.Path(path_type=Path),
    default=DEFAULT_REPORT_OUT,
    show_default=True,
    help="Directorio para los reports markdown timestamped.",
)
@click.option(
    "--target-wall-seconds",
    type=float,
    default=300.0,
    show_default=True,
    help="Target wall time for PASS/FAIL classification (spec S9: < 300s).",
)
@click.option(
    "--target-peak-mb",
    type=float,
    default=500.0,
    show_default=True,
    help="Target peak memory for PASS/FAIL classification (spec S9: < 500 MB).",
)
@click.option("--verbose", "-v", is_flag=True)
def main(
    proveedores: Path,
    articulos: Path,
    articulos_proveedores: Path,
    report_out: Path,
    target_wall_seconds: float,
    target_peak_mb: float,
    verbose: bool,
) -> None:
    """Dry-run the full XLS import extract pipeline against real data."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    # Suppress per-row WARN spam from articulos_proveedores extract — we
    # already aggregate the count in the report.
    if not verbose:
        logging.getLogger("etl.xls.articulos_proveedores").setLevel(logging.ERROR)
        logging.getLogger("etl.xls.articulos").setLevel(logging.ERROR)
        logging.getLogger("etl.xls.proveedores").setLevel(logging.ERROR)

    # Late imports — depend on BACKEND_ROOT in sys.path.
    from app import create_app
    from app.extensions import db as _db

    from etl.xls.mappers import (
        articulos_proveedores_xls,
        articulos_xls,
        proveedores_xls,
    )

    click.echo("[dry-run-real] starting tracemalloc + perf timer")
    tracemalloc.start()
    t_start = time.perf_counter()

    flask_app = create_app()
    with flask_app.app_context():
        session = _db.session

        # ----- Phase A: FK caches (read-only) ---------------------------
        t0 = time.perf_counter()
        articulos_fk_caches = articulos_xls.build_fk_caches(session)
        ap_fk_caches_db = articulos_proveedores_xls.build_fk_caches(session)
        # Snapshot DB-only proveedor cache for the proveedores extract
        # would-import reconciliation.
        proveedores_in_db: set[str] = set(articulos_fk_caches["proveedor"].keys())
        t_fk_caches = time.perf_counter() - t0
        click.echo(
            f"[dry-run-real] FK caches: prov_in_db={len(proveedores_in_db)} "
            f"familias={len(articulos_fk_caches['familia'])} "
            f"rubros={len(articulos_fk_caches['rubro'])} "
            f"articulos_in_db={len(ap_fk_caches_db['articulo'])} "
            f"({t_fk_caches:.2f}s)"
        )

        # ----- Phase B: proveedores extract ------------------------------
        t0 = time.perf_counter()
        prov_rows = list(
            proveedores_xls.extract(proveedores, sheet_name="proveedor")
        )
        t_proveedores = time.perf_counter() - t0
        # Approximate raw count by re-reading the sheet (header consumed by extract).
        # Cheaper alternative: peek at xlrd directly.
        from etl.xls.mappers.common_xls import xlrd as _xlrd  # noqa: F401
        import xlrd
        wb = xlrd.open_workbook(str(proveedores), on_demand=True)
        try:
            prov_raw_count = wb.sheet_by_name("proveedor").nrows - 1  # exclude header
        finally:
            wb.release_resources()
        prov_junk = prov_raw_count - len(prov_rows)
        click.echo(
            f"[dry-run-real] proveedores: raw={prov_raw_count} valid={len(prov_rows)} "
            f"junk={prov_junk} ({t_proveedores:.2f}s)"
        )

        # Build the synthetic post-import proveedor cache: existing DB +
        # all NEW codigos extracted (NOT in DB). This makes articulos
        # extract see realistic FK resolution.
        synthetic_proveedor_cache = dict(articulos_fk_caches["proveedor"])
        next_pid = max(synthetic_proveedor_cache.values(), default=0) + 1
        for r in prov_rows:
            cod = r["codigo"]
            if cod not in synthetic_proveedor_cache:
                synthetic_proveedor_cache[cod] = next_pid
                next_pid += 1

        # ----- Phase C: articulos extract --------------------------------
        # Use the synthetic proveedor cache so FK resolution reflects the
        # post-import state (otherwise ~all proveedor FKs would be NULL).
        articulos_fk_caches_synth = dict(articulos_fk_caches)
        articulos_fk_caches_synth["proveedor"] = synthetic_proveedor_cache

        t0 = time.perf_counter()
        art_rows, legacy_catalog, compra_zero = articulos_xls.extract(
            articulos,
            sheet_name="Sheet1",
            fk_caches=articulos_fk_caches_synth,
            skip_compra_cero=False,  # default OFF — count compra=0 as imported
        )
        t_articulos = time.perf_counter() - t0
        wb = xlrd.open_workbook(str(articulos), on_demand=True)
        try:
            art_raw_count = wb.sheet_by_name("Sheet1").nrows - 1
        finally:
            wb.release_resources()
        art_junk = art_raw_count - len(art_rows)
        # FK NULL = articulos with proveedor_principal_id is None (resolved
        # against the SYNTHETIC cache; only truly absent codigos remain NULL).
        fk_null_articulos: list[tuple[str, str, str]] = []
        for r in art_rows:
            if r["proveedor_principal_id"] is None:
                # Find the original raw proveedor code from warns (best-effort).
                raw_prov = ""
                for w in r.get("_warns", []) or []:
                    if "proveedor codigo" in w and "not found" in w:
                        # Extract "{codigo}" between single quotes.
                        try:
                            raw_prov = w.split("'")[1] if "'" in w else ""
                        except Exception:
                            raw_prov = ""
                        break
                fk_null_articulos.append((r["codigo"], r["descripcion"], raw_prov))
        click.echo(
            f"[dry-run-real] articulos: raw={art_raw_count} valid={len(art_rows)} "
            f"junk={art_junk} fk_null_proveedor={len(fk_null_articulos)} "
            f"compra_zero={len(compra_zero)} ({t_articulos:.2f}s)"
        )

        # Build synthetic articulo cache for AP extract (DB articulos + new ones).
        synthetic_articulo_cache = dict(ap_fk_caches_db["articulo"])
        next_aid = max(synthetic_articulo_cache.values(), default=0) + 1
        for r in art_rows:
            cod = r["codigo"]
            if cod not in synthetic_articulo_cache:
                synthetic_articulo_cache[cod] = next_aid
                next_aid += 1

        # ----- Phase D: articulos_proveedores extract --------------------
        ap_fk_caches_synth = {
            "articulo": synthetic_articulo_cache,
            "proveedor": synthetic_proveedor_cache,
        }
        t0 = time.perf_counter()
        ap_rows_iter = articulos_proveedores_xls.extract(
            articulos_proveedores,
            sheet_name="RELACION PRODUCTOS PROVEEDOR",
            fk_caches=ap_fk_caches_synth,
        )
        # Materialize so we can count both "would-import" and "skipped".
        ap_rows = list(ap_rows_iter)
        t_ap = time.perf_counter() - t0
        wb = xlrd.open_workbook(str(articulos_proveedores), on_demand=True)
        try:
            ap_raw_count = wb.sheet_by_name("RELACION PRODUCTOS PROVEEDOR").nrows - 1
        finally:
            wb.release_resources()
        ap_skipped_fk = sum(1 for r in ap_rows if r.get("_skip"))
        ap_would_import = sum(1 for r in ap_rows if not r.get("_skip"))
        # ap_junk = raw - all yields - skipped (yields include _skip rows;
        # extract does NOT yield junk-filtered rows, so junk = raw - yields).
        ap_junk = ap_raw_count - len(ap_rows)
        click.echo(
            f"[dry-run-real] articulos_proveedores: raw={ap_raw_count} "
            f"yielded={len(ap_rows)} junk={ap_junk} "
            f"fk_skipped={ap_skipped_fk} would_import={ap_would_import} "
            f"({t_ap:.2f}s)"
        )

    # ----- Profile finalize -------------------------------------------------
    elapsed = time.perf_counter() - t_start
    # tracemalloc.get_traced_memory() returns BYTES, not KB. Convert to MB.
    current_bytes, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    peak_mb = peak_bytes / (1024 * 1024)
    rss_mb = _rss_mb()  # may be None

    profile = {
        "wall_seconds": elapsed,
        "peak_mb_tracemalloc": peak_mb,
        "rss_mb": rss_mb,
        "phase_fk_caches_s": t_fk_caches,
        "phase_proveedores_s": t_proveedores,
        "phase_articulos_s": t_articulos,
        "phase_ap_s": t_ap,
    }
    profile_pass = {
        "wall": elapsed < target_wall_seconds,
        "memory": (
            (rss_mb if rss_mb is not None else peak_mb) < target_peak_mb
        ),
    }
    targets = {"wall_seconds": target_wall_seconds, "peak_mb": target_peak_mb}

    # Distinct counts derived from legacy_catalog (tuples shape:
    # (codigo, rubro, grupo, marca, grupdesc, categoria))
    distinct = {
        "rubros": len({t[1] for t in legacy_catalog if t[1]}),
        "grupos": len({t[2] for t in legacy_catalog if t[2]}),
        "marcas": len({t[3] for t in legacy_catalog if t[3]}),
        "grupdesc": len({t[4] for t in legacy_catalog if t[4]}),
        "categorias": len({t[5] for t in legacy_catalog if t[5]}),
    }
    counts = {
        "Proveedor": {
            "raw": prov_raw_count,
            "junk": prov_junk,
            "fk_unresolved": "n/a",
            "would_import": len(prov_rows),
        },
        "Articulo": {
            "raw": art_raw_count,
            "junk": art_junk,
            "fk_unresolved": len(fk_null_articulos),
            "would_import": len(art_rows),
        },
        "ArticuloProveedor": {
            "raw": ap_raw_count,
            "junk": ap_junk,
            "fk_unresolved": ap_skipped_fk,
            "would_import": ap_would_import,
        },
    }
    sources = {
        "proveedores": str(proveedores),
        "articulos": str(articulos),
        "articulos_proveedores": str(articulos_proveedores),
    }
    ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    md = _render_report(
        ts_iso=ts_iso,
        sources=sources,
        counts=counts,
        distinct=distinct,
        fk_null_articulos=fk_null_articulos,
        compra_zero=compra_zero,
        profile=profile,
        profile_pass=profile_pass,
        targets=targets,
    )

    # File output: filename uses Windows-friendly basic ISO format (no colons).
    out_dir = Path(report_out)
    out_dir.mkdir(parents=True, exist_ok=True)
    fname_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_file = out_dir / f"dry-run-real-{fname_ts}.md"
    out_file.write_text(md, encoding="utf-8")
    click.echo(f"[dry-run-real] report written: {out_file}")
    click.echo(
        f"[dry-run-real] PROFILE wall={elapsed:.2f}s "
        f"peak_mem_tracemalloc={peak_mb:.2f}MB "
        f"rss={rss_mb if rss_mb is not None else 'n/a'} "
        f"PASS_wall={profile_pass['wall']} PASS_mem={profile_pass['memory']}"
    )


if __name__ == "__main__":
    main()
