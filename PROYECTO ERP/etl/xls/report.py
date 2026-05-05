"""XLS Import Report writer — markdown output per spec S12.

Build a `Report` instance with run metadata + per-entity `LoadReport` objects +
`legacy_catalog` + `compra_zero` lists from `articulos_xls.extract`, call
`to_markdown()` to render, and `write_report(report, out_dir)` to persist.

## Contract (spec S12 — `sdd/importacion-xls-legacy/spec`)

`to_markdown()` MUST emit these sections, in order:

1. Header — title with ISO timestamp, source files, duration, exit status.
2. `## Counts` — table per entity (Inserted | Updated | Skipped | Errors).
3. `## Articulos con compra=0` — list (first 20 + "and N more" if > 20).
4. `## FK no resueltos` — proveedor / familia / rubro misses, fallback aplicado.
5. `## Raw catalog values preserved` — first 20 rows from legacy_catalog
   (codigo + raw values) + "and N more".
6. `## Distinct catalog values seen` — counts of distinct rubros/grupos/marcas/
   grupdesc/categorias derived from legacy_catalog (expected ~612 rubros,
   ~2052 marcas on real data).
7. `## Sheets skipped` — sheets deferred from this import (e.g. EMPAQUETADOS
   DE PRODUCTOS pending the multi-codigo model). Each entry is `{sheet} —
   {reason}`. Empty list renders as `(none)`.
8. `## Junk filtered` — first 20 + "and N more".
9. `## Errors` — first 20 + "and N more".

Empty sections render as `(none)`.

## File output

`write_report(report, out_dir)` writes TWO copies (per spec — Windows compat):

- `{out_dir}/xls-import-{YYYYMMDDTHHMMSSZ}.md` — timestamped, immutable history
- `{out_dir}/last-report.md` — overwrites on each run, "latest" mirror

UTF-8 encoded. `out_dir.mkdir(parents=True, exist_ok=True)` is called.

## Why the "first 20 + and N more" pattern

Real data has 798 compra=0 rows and up to 34843 legacy_catalog rows. Inlining
them all would produce a 1+ MB markdown file unusable by humans. The
orchestrator's hard rule for Phase 6 mandates this truncation.

## Sources of warnings

Each `LoadReport.warnings` is a list of `WarningRecord(entity, identifier,
reason)`. Sections 4/7/8 are populated by classifying the `reason` text:

- contains "not found" or "no encontrado" → FK unresolved
- contains "junk" or "codigo vacio" → junk filtered (NOTE: current xls
  mappers log junk at INFO level only, not via `report.warn` — passed as a
  separate `junk_filtered` arg for forward compatibility / tests)
- contains "error al cargar" → errors
- everything else (intra-sheet duplicate, fallback aplicado, compra=0
  audit) → silent (covered by other sections)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mappers.common import LoadReport, WarningRecord


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Max rows to inline before "... and N more" truncation in long sections.
SECTION_TRUNCATE_AT = 20

#: Valid exit statuses for the report header.
EXIT_STATUS_VALUES = ("success", "partial", "failure")


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

@dataclass
class Report:
    """Aggregated XLS import run report.

    Construct after ALL phases (proveedores / articulos / articulos_proveedores)
    have completed (or failed). All fields are required EXCEPT the warning lists
    (`fk_unresolved`, `junk_filtered`, `errors`) which default to empty.

    Attributes:
        source_proveedores: Path to the .xls used for the proveedor sheet.
        source_articulos: Path to the .xls used for Sheet1.
        source_articulos_proveedores: Path to the .xls used for the RELACION sheet.
        timestamp: ISO 8601 UTC timestamp string (e.g. "2026-05-04T23:40:00Z").
        duration_seconds: Wall-clock duration of the full run.
        exit_status: One of "success" / "partial" / "failure".
        load_reports: dict mapping entity name -> `LoadReport`. Expected keys:
          `"Proveedor"`, `"Articulo"`, `"ArticuloProveedor"`.
        legacy_catalog: list of tuples `(codigo, raw_rubro, raw_grupo,
          raw_marca, raw_grupdesc, raw_categoria)` from `articulos_xls.extract`.
        compra_zero: list of tuples `(codigo, descripcion)` from
          `articulos_xls.extract`.
        fk_unresolved: optional override for FK warnings — defaults to deriving
          from `load_reports`.
        sheets_skipped: list of `(sheet_name, reason)` tuples for sheets
          deferred from this import. Defaults to a single entry for
          `EMPAQUETADOS DE PRODUCTOS` (deferred to the multi-codigo change).
          Future imports that pick up that sheet should pass `sheets_skipped=[]`
          (or omit the entry) when constructing the Report.
        junk_filtered: optional list of junk-filtered rows (free-form strings).
          Defaults to empty (current mappers log junk at INFO, not as warnings).
        errors: optional list of error strings. Defaults to empty.
    """

    source_proveedores: str
    source_articulos: str
    source_articulos_proveedores: str
    timestamp: str
    duration_seconds: float
    exit_status: str
    load_reports: dict  # entity_name -> LoadReport
    legacy_catalog: list = field(default_factory=list)
    compra_zero: list = field(default_factory=list)
    fk_unresolved: list = field(default_factory=list)
    sheets_skipped: list = field(
        default_factory=lambda: [
            ("EMPAQUETADOS DE PRODUCTOS", "pending multi-codigo model (next change)"),
        ]
    )
    junk_filtered: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    # ---- public API ------------------------------------------------------

    def to_markdown(self) -> str:
        """Render the report as markdown matching spec S12 exactly."""
        lines: list[str] = []
        lines.extend(self._header_lines())
        lines.append("")
        lines.extend(self._counts_lines())
        lines.append("")
        lines.extend(self._compra_zero_lines())
        lines.append("")
        lines.extend(self._fk_unresolved_lines())
        lines.append("")
        lines.extend(self._raw_catalog_lines())
        lines.append("")
        lines.extend(self._distinct_counts_lines())
        lines.append("")
        lines.extend(self._sheets_skipped_lines())
        lines.append("")
        lines.extend(self._junk_filtered_lines())
        lines.append("")
        lines.extend(self._errors_lines())
        return "\n".join(lines) + "\n"

    # ---- section renderers ----------------------------------------------

    def _header_lines(self) -> list[str]:
        sources = ", ".join(
            sorted(
                {
                    self.source_proveedores,
                    self.source_articulos,
                    self.source_articulos_proveedores,
                }
            )
        )
        return [
            f"# XLS Import Report — {self.timestamp}",
            f"- Source files: {sources}",
            f"- Duration: {self.duration_seconds:.2f}s",
            f"- Exit: {self.exit_status}",
        ]

    def _counts_lines(self) -> list[str]:
        out = [
            "## Counts",
            "",
            "| Entity | Inserted | Updated | Skipped | Errors |",
            "|---|---|---|---|---|",
        ]
        for entity in ("Proveedor", "Articulo", "ArticuloProveedor"):
            r = self.load_reports.get(entity)
            if r is None:
                out.append(f"| {entity} | 0 | 0 | 0 | 0 |")
            else:
                out.append(
                    f"| {entity} | {r.inserted} | {r.updated} | "
                    f"{r.skipped} | {r.failed} |"
                )
        return out

    def _compra_zero_lines(self) -> list[str]:
        out = ["## Articulos con compra=0"]
        if not self.compra_zero:
            out.append("(none)")
            return out
        rendered = [f"- {codigo} — {descripcion}" for codigo, descripcion in self.compra_zero]
        out.extend(_truncate(rendered, SECTION_TRUNCATE_AT))
        return out

    def _fk_unresolved_lines(self) -> list[str]:
        out = ["## FK no resueltos"]
        items = self.fk_unresolved or self._collect_fk_unresolved()
        if not items:
            out.append("(none)")
            return out
        out.extend(_truncate(items, SECTION_TRUNCATE_AT))
        return out

    def _raw_catalog_lines(self) -> list[str]:
        out = ["## Raw catalog values preserved"]
        if not self.legacy_catalog:
            out.append("(none)")
            return out
        rendered = [
            (
                f'- {codigo}: rubro="{raw_rubro or ""}" '
                f'grupo="{raw_grupo or ""}" '
                f'marca="{raw_marca or ""}" '
                f'grupdesc="{raw_grupdesc or ""}" '
                f'categoria="{raw_categoria or ""}"'
            )
            for (
                codigo,
                raw_rubro,
                raw_grupo,
                raw_marca,
                raw_grupdesc,
                raw_categoria,
            ) in self.legacy_catalog
        ]
        out.extend(_truncate(rendered, SECTION_TRUNCATE_AT))
        return out

    def _distinct_counts_lines(self) -> list[str]:
        # Tuples in legacy_catalog: (codigo, rubro, grupo, marca, grupdesc, categoria)
        rubros = {r for _, r, _, _, _, _ in self.legacy_catalog if r}
        grupos = {g for _, _, g, _, _, _ in self.legacy_catalog if g}
        marcas = {m for _, _, _, m, _, _ in self.legacy_catalog if m}
        grupdesc = {gd for _, _, _, _, gd, _ in self.legacy_catalog if gd}
        categorias = {c for _, _, _, _, _, c in self.legacy_catalog if c}
        return [
            "## Distinct catalog values seen",
            f"- Distinct rubros: {len(rubros)}",
            f"- Distinct grupos (familias): {len(grupos)}",
            f"- Distinct marcas: {len(marcas)}",
            f"- Distinct grupdesc: {len(grupdesc)}",
            f"- Distinct categorias: {len(categorias)}",
        ]

    def _sheets_skipped_lines(self) -> list[str]:
        """Render `## Sheets skipped` (S12 — deferred sheets list).

        Each entry is rendered as `- {sheet} — {reason}`. Empty list shows
        `(none)`. The default value lists EMPAQUETADOS DE PRODUCTOS — see
        the dataclass docstring; future changes that import it should
        construct the Report with `sheets_skipped=[]`.
        """
        out = ["## Sheets skipped"]
        if not self.sheets_skipped:
            out.append("(none)")
            return out
        out.extend(
            _truncate(
                [f"- {sheet} — {reason}" for sheet, reason in self.sheets_skipped],
                SECTION_TRUNCATE_AT,
            )
        )
        return out

    def _junk_filtered_lines(self) -> list[str]:
        out = ["## Junk filtered"]
        if not self.junk_filtered:
            out.append("(none)")
            return out
        out.extend(_truncate([f"- {item}" for item in self.junk_filtered], SECTION_TRUNCATE_AT))
        return out

    def _errors_lines(self) -> list[str]:
        out = ["## Errors"]
        items = self.errors or self._collect_errors()
        if not items:
            out.append("(none)")
            return out
        out.extend(_truncate(items, SECTION_TRUNCATE_AT))
        return out

    # ---- warning classification -----------------------------------------

    def _collect_fk_unresolved(self) -> list[str]:
        """Filter `LoadReport.warnings` for FK-miss entries.

        Heuristic: reason contains "not found" or "no encontrado" or
        "no mapeados" or "fallback".
        """
        out: list[str] = []
        for entity, lr in self.load_reports.items():
            for w in getattr(lr, "warnings", []):
                reason = (w.reason or "").lower()
                if any(
                    needle in reason
                    for needle in ("not found", "no encontrado", "no mapeados", "fallback")
                ):
                    out.append(f"- {entity} {w.identifier}: {w.reason}")
        return out

    def _collect_errors(self) -> list[str]:
        """Filter `LoadReport.warnings` for error entries.

        Heuristic: reason contains "error al cargar" (raised in load() except
        blocks across all xls mappers).
        """
        out: list[str] = []
        for entity, lr in self.load_reports.items():
            for w in getattr(lr, "warnings", []):
                reason = (w.reason or "").lower()
                if "error al cargar" in reason:
                    out.append(f"- {entity} {w.identifier}: {w.reason}")
        return out


# ---------------------------------------------------------------------------
# File output
# ---------------------------------------------------------------------------

def write_report(report: Report, out_dir: Path) -> tuple[Path, Path]:
    """Write the report to two files: timestamped + last-report.md mirror.

    The timestamp in the filename is in UTC ISO basic format (no colons —
    Windows-friendly): ``xls-import-{YYYYMMDDTHHMMSSZ}.md``.

    Both files contain the SAME content (we use copy semantics, not symlink,
    because Windows requires admin privilege for symlink creation).

    Args:
        report: a fully-constructed `Report` instance.
        out_dir: directory to write into. Created if missing.

    Returns:
        `(timestamped_path, last_report_path)` for echoing in the CLI.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    timestamped = out_dir / f"xls-import-{ts}.md"
    last = out_dir / "last-report.md"
    md = report.to_markdown()
    timestamped.write_text(md, encoding="utf-8")
    last.write_text(md, encoding="utf-8")
    return timestamped, last


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _truncate(items: list[str], limit: int) -> list[str]:
    """Return the first `limit` items, then `"... and N more"` if applicable."""
    if len(items) <= limit:
        return items
    head = items[:limit]
    return head + [f"... and {len(items) - limit} more"]
