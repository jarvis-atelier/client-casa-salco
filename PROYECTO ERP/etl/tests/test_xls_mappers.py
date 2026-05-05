"""Tests for the .xls importer (Phases 7 + 8 of importacion-xls-legacy).

Covers:
- Phase 7 (unit): decode_xls_str, junk filter, unidad mapping, raw catalog values.
- Phase 8 (integration): each mapper end-to-end against synthetic fixtures
  built by `etl/tests/fixtures/xls_synthetic/build.py`.

Test DB: in-memory SQLite via the existing `etl/tests/conftest.py` fixtures.
The fallback taxonomy (sin-familia / sin-rubro) is seeded by calling
`backend.app.seeds.big._seed_taxonomia` on each test that needs it (the
conftest does NOT seed automatically).

Style mirrors `etl/tests/test_mappers.py` (DBF importer tests):
- Class per mapper / concern
- Decimal/UnidadMedidaEnum imports localized to test bodies that need them
- pytest.fixture for the synthetic file paths
"""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

# Ensure backend importable. conftest already prepends backend, but unit tests
# below import directly from the etl mappers and rely on it.
from app.models import Articulo, ArticuloProveedor, Familia, Proveedor, Rubro
from app.models.articulo import UnidadMedidaEnum
from app.seeds.big import _seed_taxonomia

from app.models.articulo_codigo import ArticuloCodigo, TipoCodigoArticuloEnum

from etl.xls.mappers import articulos_proveedores_xls as m_artprov_xls
from etl.xls.mappers import articulos_xls as m_articulos_xls
from etl.xls.mappers import empaquetados_xls as m_empaquetados_xls
from etl.xls.mappers import proveedores_xls as m_proveedores_xls
from etl.xls.mappers.common_xls import decode_xls_str
from etl.xls.report import Report

# Path to fixtures committed alongside the build.py script.
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures" / "xls_synthetic"
PROVEEDORES_XLS = FIXTURES_DIR / "proveedores.xls"
ARTICULOS_XLS = FIXTURES_DIR / "articulos.xls"
ARTPROV_XLS = FIXTURES_DIR / "articulos_proveedores.xls"
EMPAQUETADOS_XLS = FIXTURES_DIR / "empaquetados.xls"


@pytest.fixture
def fixtures_present():
    for p in (PROVEEDORES_XLS, ARTICULOS_XLS, ARTPROV_XLS, EMPAQUETADOS_XLS):
        assert p.exists(), (
            f"Missing fixture {p}. Regenerate with: "
            "python etl/tests/fixtures/xls_synthetic/build.py"
        )
    return {
        "proveedores": PROVEEDORES_XLS,
        "articulos": ARTICULOS_XLS,
        "articulos_proveedores": ARTPROV_XLS,
        "empaquetados": EMPAQUETADOS_XLS,
    }


@pytest.fixture
def seeded_taxonomia(session):
    """Seed sin-familia / sin-rubro fallbacks on the in-memory test DB.

    Conftest creates a fresh DB per test (`_db.create_all()` then
    `_db.drop_all()`) but does NOT seed taxonomy. The articulos importer
    requires `sin-familia`/`sin-rubro` to exist (it does NOT auto-create
    per orchestrator hard rule). We invoke the same idempotent
    `_seed_taxonomia` used by `flask seed big`.
    """
    _seed_taxonomia(echo=lambda *_a, **_kw: None)
    session.commit()
    return session


# ===========================================================================
# Phase 7 — UNIT TESTS
# ===========================================================================


# ---------------------------------------------------------------------------
# 7.1 decode_xls_str roundtrip
# ---------------------------------------------------------------------------


class TestDecodeXlsStr:
    """Test matrix from design Section 2.

    NOTE: All cases are *idempotent* — strings already-correctly-decoded as
    cp1252 (since latin-1 and cp1252 agree in 0xA0-0xFF) pass through unchanged.
    The function's repair value shines on cp1252-specific high bytes
    (0x80-0x9F, e.g. U+20AC euro sign) that wouldn't be valid latin-1, but
    those don't appear in the spec test matrix.
    """

    @pytest.mark.parametrize(
        "input_str, expected",
        [
            ("C\xf3digo", "C\xf3digo"),       # "Código"
            ("Espa\xf1a", "Espa\xf1a"),       # "España"
            ("nu\xf1ez", "nu\xf1ez"),         # "nuñez"
            ("mu\xf1ec\xf3n", "mu\xf1ec\xf3n"),  # "muñecón"
            ("YERBA", "YERBA"),               # already correct
            (None, None),
            (123, 123),                       # int passthrough
            (12.5, 12.5),                     # float passthrough
        ],
    )
    def test_roundtrip_matrix(self, input_str, expected):
        assert decode_xls_str(input_str) == expected

    def test_idempotent(self):
        # decode(decode(x)) == decode(x)
        for s in ("Código", "España", "muñecón", "YERBA"):
            assert decode_xls_str(decode_xls_str(s)) == decode_xls_str(s)


# ---------------------------------------------------------------------------
# 7.2 Junk filter — exercise per-mapper filter logic via in-memory rows
# ---------------------------------------------------------------------------


class TestJunkFilter:
    """Validate junk-row filter behavior in extract().

    Each mapper drops rows where:
      - codigo is empty / None / '0000'
      - codigo == descripcion (proveedores: codigo == nombre)
      - descripcion (or nombre) matches /^test|^prueba|^xxx/i (case-insensitive)

    We exercise the filter by calling extract() on the synthetic fixture and
    asserting the junk rows DON'T appear in the output. Pure-row unit tests
    aren't possible because the mappers read directly from xls files via
    `read_sheet`. The fixture has explicit junk rows for this purpose.
    """

    def test_proveedores_filters_junk(self, fixtures_present):
        rows = list(
            m_proveedores_xls.extract(fixtures_present["proveedores"], sheet_name="proveedor")
        )
        codigos = {r["codigo"] for r in rows}
        # `0000` is junk.
        assert "0000" not in codigos
        # codigo==nombre row ("BASURA"/"BASURA") is junk.
        assert "BASURA" not in codigos
        # Valid rows survive.
        assert {"P001", "P002", "P003"}.issubset(codigos)

    def test_articulos_filters_junk(self, session, seeded_taxonomia, fixtures_present):
        # articulos.extract requires fk_caches; build them on the seeded DB.
        # No proveedores yet -> proveedor cache is empty (FKs will resolve to None).
        fk = m_articulos_xls.build_fk_caches(session)
        rows, _legacy, _czero = m_articulos_xls.extract(
            fixtures_present["articulos"], sheet_name="Sheet1", fk_caches=fk
        )
        codigos = [r["codigo"] for r in rows]
        # `0000` junk row is filtered.
        assert "0000" not in codigos
        # Valid rows survive (note ART01 appears twice — duplicate is preserved
        # in extract; load() handles last-wins).
        assert "ART01" in codigos
        assert codigos.count("ART01") == 2

    def test_articulos_proveedores_filters_junk(
        self, session, seeded_taxonomia, fixtures_present
    ):
        # Need at least Articulo + Proveedor rows for cache; insert minimal.
        from etl.xls.mappers import articulos_xls
        # Seed proveedores from fixture:
        prov_rows = list(
            m_proveedores_xls.extract(fixtures_present["proveedores"], sheet_name="proveedor")
        )
        m_proveedores_xls.load(session, prov_rows)
        session.commit()
        # Seed articulos:
        fk_art = articulos_xls.build_fk_caches(session)
        art_rows, _l, _c = articulos_xls.extract(
            fixtures_present["articulos"], sheet_name="Sheet1", fk_caches=fk_art
        )
        articulos_xls.load(session, art_rows)
        session.commit()
        fk_ap = m_artprov_xls.build_fk_caches(session)
        rows = list(
            m_artprov_xls.extract(
                fixtures_present["articulos_proveedores"],
                sheet_name="RELACION PRODUCTOS PROVEEDOR",
                fk_caches=fk_ap,
            )
        )
        # Skip rows are still yielded (with `_skip=True`); count actual pairs.
        valid_rows = [r for r in rows if not r.get("_skip")]
        # Fixture has 5 rows: 2 normal + 1 missing prov + 1 missing art + 1 cantidad=5.
        # Valid (resolvable) pairs = 2 normal + 1 cantidad=5 = 3.
        assert len(valid_rows) == 3
        # Skip rows = 2 (missing prov + missing art).
        skip_rows = [r for r in rows if r.get("_skip")]
        assert len(skip_rows) == 2


# ---------------------------------------------------------------------------
# 7.3 Unidad medida mapping
# ---------------------------------------------------------------------------


class TestUnidadMapping:
    @pytest.mark.parametrize(
        "raw, expected",
        [
            ("K", UnidadMedidaEnum.kg),
            ("KG", UnidadMedidaEnum.kg),
            ("k", UnidadMedidaEnum.kg),       # case-insensitive
            ("kg", UnidadMedidaEnum.kg),
            ("U", UnidadMedidaEnum.unidad),
            ("UN", UnidadMedidaEnum.unidad),
            ("L", UnidadMedidaEnum.lt),
            ("LT", UnidadMedidaEnum.lt),
            ("G", UnidadMedidaEnum.gr),
            ("GR", UnidadMedidaEnum.gr),
            ("ML", UnidadMedidaEnum.ml),
            ("FOO", UnidadMedidaEnum.unidad),  # fallback
            (None, UnidadMedidaEnum.unidad),
            ("", UnidadMedidaEnum.unidad),
        ],
    )
    def test_map_unidad(self, raw, expected):
        assert m_articulos_xls._map_unidad(raw) == expected


# ---------------------------------------------------------------------------
# 7.4 Raw catalog values preservation (Decision 6 path B)
# ---------------------------------------------------------------------------


class TestRawValuesPreserved:
    """Verifies legacy_catalog accumulator captures raw rubro/grupo/marca tuples.

    Decision 6 path B: NO `Articulo.observaciones`. Raw values surface only
    in the import .md report (Phase 6) sourced from `legacy_catalog` returned
    by `articulos_xls.extract`.
    """

    def test_legacy_catalog_contains_raw_values(
        self, session, seeded_taxonomia, fixtures_present
    ):
        fk = m_articulos_xls.build_fk_caches(session)
        _rows, legacy_catalog, _czero = m_articulos_xls.extract(
            fixtures_present["articulos"], sheet_name="Sheet1", fk_caches=fk
        )
        # Tuple shape: (codigo, rubro, grupo, marca, grupdesc, categoria)
        # ART01 fixture has rubro="ALMACEN-CONDIMENTOS" grupo="ALMACEN" marca="COCINERO"
        # grupdesc="ACEITES" categoria="BASICOS".
        art01_entries = [t for t in legacy_catalog if t[0] == "ART01"]
        # ART01 appears twice (intra-sheet duplicate); both legacy entries
        # captured for audit.
        assert len(art01_entries) == 2
        first = art01_entries[0]
        assert first == (
            "ART01",
            "ALMACEN-CONDIMENTOS",
            "ALMACEN",
            "COCINERO",
            "ACEITES",
            "BASICOS",
        )


# ===========================================================================
# Phase 8 — INTEGRATION TESTS (against synthetic fixtures + in-memory DB)
# ===========================================================================


class TestImportProveedoresHappy:
    """8.3 — proveedores happy path."""

    def test_inserts_normal_skips_junk(self, session, fixtures_present):
        rows = list(
            m_proveedores_xls.extract(
                fixtures_present["proveedores"], sheet_name="proveedor"
            )
        )
        report = m_proveedores_xls.load(session, rows)
        session.commit()
        # 3 normal rows in fixture (P001 / P002 / P003); 2 junk filtered upstream.
        assert report.inserted == 3
        assert session.query(Proveedor).count() == 3
        # Mojibake decoding: P002 should have razon_social "España SA"
        # (n-tilde decoded; in the fixture it's stored as latin-1 high byte 0xf1
        # which decode_xls_str round-trips unchanged).
        p002 = session.query(Proveedor).filter_by(codigo="P002").one()
        assert "\xf1" in p002.razon_social  # n-tilde present
        assert p002.razon_social == "Espa\xf1a SA"


class TestImportArticulosHappy:
    """8.4 — articulos happy path + FK NULL warn case."""

    def test_articulos_with_proveedor_fk_resolve_or_null(
        self, session, seeded_taxonomia, fixtures_present
    ):
        # Pre-load proveedores so P001 and P003 resolve.
        prov_rows = list(
            m_proveedores_xls.extract(
                fixtures_present["proveedores"], sheet_name="proveedor"
            )
        )
        m_proveedores_xls.load(session, prov_rows)
        session.commit()

        fk = m_articulos_xls.build_fk_caches(session)
        rows, _legacy, _czero = m_articulos_xls.extract(
            fixtures_present["articulos"], sheet_name="Sheet1", fk_caches=fk
        )
        report = m_articulos_xls.load(session, rows)
        session.commit()

        # ART01 (twice — last-wins) + ART02 + ART03 + ART05 + ART06 + ART07
        # + ART09 + ART10 = 8 distinct codigos. Junk row '0000' filtered.
        assert session.query(Articulo).count() == 8

        # ART01: valid proveedor P001 -> proveedor_principal_id != NULL.
        art01 = session.query(Articulo).filter_by(codigo="ART01").one()
        assert art01.proveedor_principal_id is not None
        # And the descripcion is the SECOND row's value (last-wins).
        assert art01.descripcion == "Aceite Cocinero MODIFIED"

        # ART03 has unknown proveedor "XX999" -> proveedor_principal_id IS NULL,
        # and a WARN should have been recorded.
        art03 = session.query(Articulo).filter_by(codigo="ART03").one()
        assert art03.proveedor_principal_id is None

        warned_codigos = {w.identifier for w in report.warnings}
        # Each of these articulos has a row about FK fallback / not found.
        assert "ART03" in warned_codigos

        # All articulos fall back to sin-familia / sin-rubro because the
        # synthetic taxonomy doesn't include the rubro/grupo names.
        sin_familia = session.query(Familia).filter_by(codigo="sin-familia").one()
        sin_rubro = session.query(Rubro).filter_by(codigo="sin-rubro").one()
        for a in session.query(Articulo).all():
            assert a.familia_id == sin_familia.id
            assert a.rubro_id == sin_rubro.id
            # marca_id is NULL by design.
            assert a.marca_id is None


class TestImportArticulosProveedoresHappy:
    """8.5 — articulos_proveedores happy path."""

    def test_pairs_persisted_skips_warned(
        self, session, seeded_taxonomia, fixtures_present
    ):
        # Run all 3 phases in order.
        prov_rows = list(
            m_proveedores_xls.extract(
                fixtures_present["proveedores"], sheet_name="proveedor"
            )
        )
        m_proveedores_xls.load(session, prov_rows)
        session.commit()

        fk_art = m_articulos_xls.build_fk_caches(session)
        art_rows, _legacy, _czero = m_articulos_xls.extract(
            fixtures_present["articulos"], sheet_name="Sheet1", fk_caches=fk_art
        )
        m_articulos_xls.load(session, art_rows)
        session.commit()

        fk_ap = m_artprov_xls.build_fk_caches(session)
        ap_rows = list(
            m_artprov_xls.extract(
                fixtures_present["articulos_proveedores"],
                sheet_name="RELACION PRODUCTOS PROVEEDOR",
                fk_caches=fk_ap,
            )
        )
        report = m_artprov_xls.load(session, ap_rows)
        session.commit()

        # Fixture has 5 rows:
        #   2 normal pairs (ART09/P001, ART10/P003)
        #   1 missing proveedor FK (ART09/XX999) -> SKIP+WARN -> failed
        #   1 missing articulo FK (NOEXISTE/P001) -> SKIP+WARN -> failed
        #   1 with cantidad=5 (ART01/P001) -> normal pair, persisted to cantidad_por_pack.
        # = 3 inserted, 2 failed.
        assert report.inserted == 3
        assert report.failed == 2
        # Verify model fields and Change B re-read of cantidad -> cantidad_por_pack.
        ap_rows_db = session.query(ArticuloProveedor).all()
        assert len(ap_rows_db) == 3
        for ap in ap_rows_db:
            assert hasattr(ap, "codigo_proveedor")
            assert hasattr(ap, "costo_proveedor")
            assert hasattr(ap, "cantidad_por_pack")
            # No bare `cantidad` field — only `cantidad_por_pack`.
            assert not hasattr(ap, "cantidad")


class TestImportIdempotent:
    """8.6 — full pipeline run twice produces identical row counts."""

    def _run_full(self, session, fixtures_present):
        prov_rows = list(
            m_proveedores_xls.extract(
                fixtures_present["proveedores"], sheet_name="proveedor"
            )
        )
        rep_p = m_proveedores_xls.load(session, prov_rows)
        session.commit()

        fk_art = m_articulos_xls.build_fk_caches(session)
        art_rows, _l, _c = m_articulos_xls.extract(
            fixtures_present["articulos"], sheet_name="Sheet1", fk_caches=fk_art
        )
        rep_a = m_articulos_xls.load(session, art_rows)
        session.commit()

        fk_ap = m_artprov_xls.build_fk_caches(session)
        ap_rows = list(
            m_artprov_xls.extract(
                fixtures_present["articulos_proveedores"],
                sheet_name="RELACION PRODUCTOS PROVEEDOR",
                fk_caches=fk_ap,
            )
        )
        rep_ap = m_artprov_xls.load(session, ap_rows)
        session.commit()
        return rep_p, rep_a, rep_ap

    def test_second_run_inserts_zero(
        self, session, seeded_taxonomia, fixtures_present
    ):
        # First run: counts X inserted across the 3 entities.
        rep_p1, rep_a1, rep_ap1 = self._run_full(session, fixtures_present)
        count_p_1 = session.query(Proveedor).count()
        count_a_1 = session.query(Articulo).count()
        count_ap_1 = session.query(ArticuloProveedor).count()

        assert rep_p1.inserted == 3
        assert rep_a1.inserted == 8
        assert rep_ap1.inserted == 3

        # Second run: 0 inserted, counts identical.
        rep_p2, rep_a2, rep_ap2 = self._run_full(session, fixtures_present)
        count_p_2 = session.query(Proveedor).count()
        count_a_2 = session.query(Articulo).count()
        count_ap_2 = session.query(ArticuloProveedor).count()

        assert count_p_1 == count_p_2
        assert count_a_1 == count_a_2
        assert count_ap_1 == count_ap_2
        assert rep_p2.inserted == 0
        assert rep_a2.inserted == 0
        assert rep_ap2.inserted == 0


class TestSkipCompraCero:
    """8.7 — --skip-compra-cero flag, both ON and OFF."""

    def test_default_off_imports_compra_zero(
        self, session, seeded_taxonomia, fixtures_present
    ):
        # Pre-seed proveedores.
        prov_rows = list(
            m_proveedores_xls.extract(
                fixtures_present["proveedores"], sheet_name="proveedor"
            )
        )
        m_proveedores_xls.load(session, prov_rows)
        session.commit()

        fk = m_articulos_xls.build_fk_caches(session)
        rows, _legacy, compra_zero = m_articulos_xls.extract(
            fixtures_present["articulos"],
            sheet_name="Sheet1",
            fk_caches=fk,
            skip_compra_cero=False,
        )
        report = m_articulos_xls.load(session, rows)
        session.commit()

        # ART02 has compra=0; with flag OFF (default), it's imported.
        art02 = (
            session.query(Articulo).filter_by(codigo="ART02").one_or_none()
        )
        assert art02 is not None
        assert art02.costo == Decimal("0")
        # And compra_zero list captures it (for the report).
        assert ("ART02", "Producto Compra Cero") in compra_zero

    def test_flag_on_skips_compra_zero(
        self, session, seeded_taxonomia, fixtures_present
    ):
        prov_rows = list(
            m_proveedores_xls.extract(
                fixtures_present["proveedores"], sheet_name="proveedor"
            )
        )
        m_proveedores_xls.load(session, prov_rows)
        session.commit()

        fk = m_articulos_xls.build_fk_caches(session)
        rows, _legacy, compra_zero = m_articulos_xls.extract(
            fixtures_present["articulos"],
            sheet_name="Sheet1",
            fk_caches=fk,
            skip_compra_cero=True,
        )
        m_articulos_xls.load(session, rows)
        session.commit()

        # ART02 should NOT be in DB.
        art02 = session.query(Articulo).filter_by(codigo="ART02").one_or_none()
        assert art02 is None
        # But it IS still tracked in compra_zero (for the report — audit even
        # when skipped).
        assert ("ART02", "Producto Compra Cero") in compra_zero


class TestReportShape:
    """8.8 — report markdown contains all required sections per spec S12."""

    def test_required_sections_present(
        self, session, seeded_taxonomia, fixtures_present
    ):
        # Run a full import to populate LoadReports.
        prov_rows = list(
            m_proveedores_xls.extract(
                fixtures_present["proveedores"], sheet_name="proveedor"
            )
        )
        rep_p = m_proveedores_xls.load(session, prov_rows)
        session.commit()

        fk_art = m_articulos_xls.build_fk_caches(session)
        art_rows, legacy_catalog, compra_zero = m_articulos_xls.extract(
            fixtures_present["articulos"], sheet_name="Sheet1", fk_caches=fk_art
        )
        rep_a = m_articulos_xls.load(session, art_rows)
        session.commit()

        fk_ap = m_artprov_xls.build_fk_caches(session)
        ap_rows = list(
            m_artprov_xls.extract(
                fixtures_present["articulos_proveedores"],
                sheet_name="RELACION PRODUCTOS PROVEEDOR",
                fk_caches=fk_ap,
            )
        )
        rep_ap = m_artprov_xls.load(session, ap_rows)
        session.commit()

        report = Report(
            source_proveedores=str(fixtures_present["proveedores"]),
            source_articulos=str(fixtures_present["articulos"]),
            source_articulos_proveedores=str(fixtures_present["articulos_proveedores"]),
            timestamp="2026-05-04T23:59:59Z",
            duration_seconds=1.23,
            exit_status="success",
            load_reports={
                "Proveedor": rep_p,
                "Articulo": rep_a,
                "ArticuloProveedor": rep_ap,
            },
            legacy_catalog=legacy_catalog,
            compra_zero=compra_zero,
        )
        md = report.to_markdown()

        # Required substrings per spec S12 / B6 implementation.
        for needle in (
            "# XLS Import Report",
            "## Counts",
            "## Articulos con compra=0",
            "## FK no resueltos",
            "## Raw catalog values preserved",
            "## Distinct catalog values seen",
            "## Sheets skipped",
            "## Junk filtered",
            "## Errors",
            "Distinct rubros:",
            # S12 mandates the deferred-sheet bullet text exactly.
            "EMPAQUETADOS DE PRODUCTOS — pending multi-codigo model (next change)",
        ):
            assert needle in md, f"missing section: {needle!r}\n---\n{md}"

    def test_sheets_skipped_empty_renders_none(self):
        """Constructing Report with `sheets_skipped=[]` renders `(none)`.

        Future changes that pick up EMPAQUETADOS DE PRODUCTOS will pass an
        empty list — the section MUST still be present (per spec S12) but
        with `(none)` matching the existing empty-section convention.
        """
        from etl.mappers.common import LoadReport

        report = Report(
            source_proveedores="x.xls",
            source_articulos="y.xls",
            source_articulos_proveedores="z.xls",
            timestamp="2026-05-04T23:59:59Z",
            duration_seconds=0.0,
            exit_status="success",
            load_reports={
                "Proveedor": LoadReport(entity="Proveedor"),
                "Articulo": LoadReport(entity="Articulo"),
                "ArticuloProveedor": LoadReport(entity="ArticuloProveedor"),
            },
            sheets_skipped=[],
        )
        md = report.to_markdown()
        assert "## Sheets skipped" in md
        # The section heading is followed by `(none)` on the next line.
        section = md.split("## Sheets skipped", 1)[1]
        # Look at just the first non-empty line after the heading.
        first_body_line = next(
            line for line in section.splitlines()[1:] if line.strip()
        )
        assert first_body_line == "(none)"


class TestIntraSheetDuplicateLastWins:
    """8.9 — intra-sheet duplicate codigo: last-wins."""

    def test_duplicate_codigo_last_descripcion_wins(
        self, session, seeded_taxonomia, fixtures_present
    ):
        # Pre-seed proveedores so FKs resolve.
        prov_rows = list(
            m_proveedores_xls.extract(
                fixtures_present["proveedores"], sheet_name="proveedor"
            )
        )
        m_proveedores_xls.load(session, prov_rows)
        session.commit()

        fk = m_articulos_xls.build_fk_caches(session)
        rows, _l, _c = m_articulos_xls.extract(
            fixtures_present["articulos"], sheet_name="Sheet1", fk_caches=fk
        )
        report = m_articulos_xls.load(session, rows)
        session.commit()

        # Only one ART01 row in DB.
        art01 = session.query(Articulo).filter_by(codigo="ART01").all()
        assert len(art01) == 1
        # And its descripcion matches the SECOND occurrence (last-wins).
        assert art01[0].descripcion == "Aceite Cocinero MODIFIED"
        # A WARN was logged about the duplicate.
        warn_reasons = " ".join(w.reason for w in report.warnings)
        assert "intra-sheet duplicate" in warn_reasons


# ===========================================================================
# Change B (xls-empaquetados-y-presentaciones) — Phase 5+6 (B4)
# ===========================================================================
#
# Coverage:
#   - S2  EMPAQUETADOS happy path end-to-end (build_fk_caches + extract + load).
#   - S7  RELACION cantidad re-read into cantidad_por_pack.
#   - S8  EMPAQUETADOS load idempotency (re-run -> 0 inserts).
#   - S9  EMPAQUETADOS FK miss -> SKIP + WARN, no abort.
#   - S10 EMPAQUETADOS junk filter (codigo='0000') -> SKIP.
#   - tipo heuristic application via assign_tipos pipeline.
#   - articulos_proveedores idempotency post-cantidad-re-read.


def _seed_articulos_for_empaquetados(session, fixtures_present):
    """Helper: pre-seed proveedores + articulos so empaquetados FK resolves."""
    prov_rows = list(
        m_proveedores_xls.extract(
            fixtures_present["proveedores"], sheet_name="proveedor"
        )
    )
    m_proveedores_xls.load(session, prov_rows)
    session.commit()

    fk_art = m_articulos_xls.build_fk_caches(session)
    art_rows, _l, _c = m_articulos_xls.extract(
        fixtures_present["articulos"], sheet_name="Sheet1", fk_caches=fk_art
    )
    m_articulos_xls.load(session, art_rows)
    session.commit()


class TestEmpaquetadosExtractHappyPath:
    """S2 + S9 + S10 — extract handles FK miss + junk + tipo assignment."""

    def test_extract_returns_rows_with_tipo_skipped_for_junk_and_fk_miss(
        self, session, seeded_taxonomia, fixtures_present
    ):
        _seed_articulos_for_empaquetados(session, fixtures_present)

        fk = m_empaquetados_xls.build_fk_caches(session)
        rows, skipped = m_empaquetados_xls.extract(
            fixtures_present["empaquetados"],
            sheet_name="EMPAQUETADOS DE PRODUCTOS",
            fk_caches=fk,
        )

        # Fixture has 10 rows:
        #   1 ART01 (cant=1), 1 ART02 (cant=6),
        #   4 ART09 ([1,1,6,12]), 2 ART10 ([6,12]),
        #   1 junk codigo='0000' (FILTERED),
        #   1 FK miss "NOEXISTE" (SKIPPED+WARN).
        # Valid rows = 8, skipped = 2.
        assert len(rows) == 8
        assert len(skipped) == 2

        # Verify skip reasons (S9 FK miss + S10 junk).
        reasons = " ".join(s["reason"] for s in skipped)
        assert "FK miss" in reasons or "not found" in reasons or "skipped" in reasons
        assert "junk" in reasons or "0000" in reasons

        # Verify tipo assignment via heuristic (S3-S6).
        by_codigo = {r["codigo"]: r for r in rows}
        # ART01 single cant=1 -> principal.
        assert by_codigo["EAN-001-PRINC"]["tipo"] == TipoCodigoArticuloEnum.principal
        # ART02 single cant=6 -> first row forced principal (no unit in group).
        assert by_codigo["EAN-002-PACK"]["tipo"] == TipoCodigoArticuloEnum.principal
        # ART09 [1,1,6,12] -> EAN-009-A=principal, EAN-009-B=alterno,
        #                      EAN-009-C/D=empaquetado.
        assert by_codigo["EAN-009-A"]["tipo"] == TipoCodigoArticuloEnum.principal
        assert by_codigo["EAN-009-B"]["tipo"] == TipoCodigoArticuloEnum.alterno
        assert by_codigo["EAN-009-C"]["tipo"] == TipoCodigoArticuloEnum.empaquetado
        assert by_codigo["EAN-009-D"]["tipo"] == TipoCodigoArticuloEnum.empaquetado
        # ART10 [6,12] -> first forced principal, second empaquetado.
        assert by_codigo["EAN-010-A"]["tipo"] == TipoCodigoArticuloEnum.principal
        assert by_codigo["EAN-010-B"]["tipo"] == TipoCodigoArticuloEnum.empaquetado


class TestEmpaquetadosLoadIdempotent:
    """S8 — second run produces 0 inserts; idempotent UPDATE branch verified."""

    def _run_full(self, session, fixtures_present):
        fk = m_empaquetados_xls.build_fk_caches(session)
        rows, _skipped = m_empaquetados_xls.extract(
            fixtures_present["empaquetados"],
            sheet_name="EMPAQUETADOS DE PRODUCTOS",
            fk_caches=fk,
        )
        report = m_empaquetados_xls.load(session, rows)
        session.commit()
        return report

    def test_second_run_inserts_zero(
        self, session, seeded_taxonomia, fixtures_present
    ):
        _seed_articulos_for_empaquetados(session, fixtures_present)

        # Run 1: 8 inserts (matching valid rows from extract).
        rep1 = self._run_full(session, fixtures_present)
        assert rep1.inserted == 8
        count_after_1 = session.query(ArticuloCodigo).count()
        assert count_after_1 == 8

        # Run 2: idempotent — 0 inserts, 0 updates (tipo unchanged), all skipped.
        rep2 = self._run_full(session, fixtures_present)
        assert rep2.inserted == 0
        assert rep2.updated == 0
        assert rep2.skipped == 8
        count_after_2 = session.query(ArticuloCodigo).count()
        assert count_after_2 == count_after_1

    def test_update_branch_refreshes_tipo_when_different(
        self, session, seeded_taxonomia, fixtures_present
    ):
        """Pre-existing ArticuloCodigo row with mismatched tipo -> UPDATE."""
        _seed_articulos_for_empaquetados(session, fixtures_present)

        # Pre-create an ArticuloCodigo for ART01/EAN-001-PRINC with tipo=alterno
        # (mimics Change A backfill that may have classified differently).
        art01 = session.query(Articulo).filter_by(codigo="ART01").one()
        existing_ac = ArticuloCodigo(
            articulo_id=art01.id,
            codigo="EAN-001-PRINC",
            tipo=TipoCodigoArticuloEnum.alterno,
        )
        session.add(existing_ac)
        session.commit()

        # Run empaquetados import. Heuristic says EAN-001-PRINC -> principal,
        # so the UPDATE branch should fire.
        report = self._run_full(session, fixtures_present)

        # Verify the UPDATE happened.
        assert report.updated >= 1
        refreshed = session.query(ArticuloCodigo).filter_by(
            articulo_id=art01.id, codigo="EAN-001-PRINC"
        ).one()
        assert refreshed.tipo == TipoCodigoArticuloEnum.principal


class TestArticulosProveedoresCantidadReRead:
    """S7 + S11 — cantidad column re-read into cantidad_por_pack."""

    def test_cantidad_persisted_to_cantidad_por_pack(
        self, session, seeded_taxonomia, fixtures_present
    ):
        # Run all 3 phases: proveedores -> articulos -> articulos_proveedores.
        _seed_articulos_for_empaquetados(session, fixtures_present)

        fk_ap = m_artprov_xls.build_fk_caches(session)
        ap_rows = list(
            m_artprov_xls.extract(
                fixtures_present["articulos_proveedores"],
                sheet_name="RELACION PRODUCTOS PROVEEDOR",
                fk_caches=fk_ap,
            )
        )
        m_artprov_xls.load(session, ap_rows)
        session.commit()

        # Fixture row 5: ART01 + P001 had cantidad=5 in xls.
        # That maps to ArticuloProveedor.cantidad_por_pack = Decimal("5").
        art01 = session.query(Articulo).filter_by(codigo="ART01").one()
        prov_p001 = session.query(Proveedor).filter_by(codigo="P001").one()
        ap = (
            session.query(ArticuloProveedor)
            .filter_by(articulo_id=art01.id, proveedor_id=prov_p001.id)
            .one()
        )
        assert ap.cantidad_por_pack == Decimal("5")

        # Other pairs had cantidad=1 -> Decimal("1").
        art09 = session.query(Articulo).filter_by(codigo="ART09").one()
        ap09 = (
            session.query(ArticuloProveedor)
            .filter_by(articulo_id=art09.id, proveedor_id=prov_p001.id)
            .one()
        )
        assert ap09.cantidad_por_pack == Decimal("1")

    def test_idempotent_when_cantidad_unchanged(
        self, session, seeded_taxonomia, fixtures_present
    ):
        _seed_articulos_for_empaquetados(session, fixtures_present)

        fk_ap = m_artprov_xls.build_fk_caches(session)
        rows1 = list(
            m_artprov_xls.extract(
                fixtures_present["articulos_proveedores"],
                sheet_name="RELACION PRODUCTOS PROVEEDOR",
                fk_caches=fk_ap,
            )
        )
        rep1 = m_artprov_xls.load(session, rows1)
        session.commit()
        assert rep1.inserted == 3

        # Second run: extract + load, same input -> 0 inserts, 0 updates.
        rows2 = list(
            m_artprov_xls.extract(
                fixtures_present["articulos_proveedores"],
                sheet_name="RELACION PRODUCTOS PROVEEDOR",
                fk_caches=fk_ap,
            )
        )
        rep2 = m_artprov_xls.load(session, rows2)
        session.commit()
        assert rep2.inserted == 0
        assert rep2.updated == 0
        assert rep2.skipped == 3

    def test_update_path_refreshes_cantidad_when_different(
        self, session, seeded_taxonomia, fixtures_present
    ):
        """Pre-existing ArticuloProveedor with cantidad_por_pack=1 -> UPDATE to 5."""
        _seed_articulos_for_empaquetados(session, fixtures_present)

        # Pre-create the ART01/P001 pair with cantidad_por_pack=Decimal("1").
        art01 = session.query(Articulo).filter_by(codigo="ART01").one()
        prov_p001 = session.query(Proveedor).filter_by(codigo="P001").one()
        existing_ap = ArticuloProveedor(
            articulo_id=art01.id,
            proveedor_id=prov_p001.id,
            codigo_proveedor="PROV-CODE-5",
            costo_proveedor=Decimal("0"),
            cantidad_por_pack=Decimal("1"),
        )
        session.add(existing_ap)
        session.commit()

        # Now run the importer. xls says cantidad=5 for ART01/P001.
        fk_ap = m_artprov_xls.build_fk_caches(session)
        ap_rows = list(
            m_artprov_xls.extract(
                fixtures_present["articulos_proveedores"],
                sheet_name="RELACION PRODUCTOS PROVEEDOR",
                fk_caches=fk_ap,
            )
        )
        report = m_artprov_xls.load(session, ap_rows)
        session.commit()

        # The UPDATE branch must have fired for the cantidad delta.
        assert report.updated >= 1
        refreshed = (
            session.query(ArticuloProveedor)
            .filter_by(articulo_id=art01.id, proveedor_id=prov_p001.id)
            .one()
        )
        assert refreshed.cantidad_por_pack == Decimal("5")
