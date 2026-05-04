"""Tests de las utilidades compartidas (sanitizacion + mapeo de enums)."""
from __future__ import annotations

from decimal import Decimal

from mappers.common import (
    NUIV_TO_CONDICION_IVA,
    bool_from_legacy,
    clean_str,
    decimal_or_zero,
    int_or_none,
    sanitize_text,
    unidad_medida_from_legacy,
)
from app.models.articulo import UnidadMedidaEnum
from app.models.cliente import CondicionIvaEnum


class TestCleanStr:
    def test_none_returns_none(self):
        assert clean_str(None) is None

    def test_empty_string_returns_none(self):
        assert clean_str("") is None
        assert clean_str("   ") is None

    def test_strips_and_collapses_whitespace(self):
        assert clean_str("  hola   mundo  ") == "hola mundo"

    def test_removes_null_bytes(self):
        assert clean_str("hola\x00mundo") == "holamundo"

    def test_truncates_to_max_len(self):
        assert clean_str("a" * 100, max_len=10) == "a" * 10

    def test_non_string_coerced(self):
        assert clean_str(123) == "123"


class TestSanitizeText:
    def test_normalizes_unicode(self):
        # NFC: "e" + combining acute -> "é"
        s = "café"
        assert sanitize_text(s) == "café"

    def test_none_passes_through(self):
        assert sanitize_text(None) is None


class TestDecimalOrZero:
    def test_none_is_zero(self):
        assert decimal_or_zero(None) == Decimal("0")

    def test_empty_string_is_zero(self):
        assert decimal_or_zero("") == Decimal("0")

    def test_float_preserves_precision_via_str(self):
        # 0.1 en float es 0.1000000000000000055... -> via str deberia quedar 0.1
        result = decimal_or_zero(0.1, places=4)
        assert result == Decimal("0.1000")

    def test_invalid_returns_zero(self):
        assert decimal_or_zero("pepito") == Decimal("0")

    def test_existing_decimal_passes_through(self):
        d = Decimal("5.25")
        assert decimal_or_zero(d) == d


class TestIntOrNone:
    def test_none(self):
        assert int_or_none(None) is None

    def test_valid(self):
        assert int_or_none("42") == 42
        assert int_or_none(42.0) == 42

    def test_invalid(self):
        assert int_or_none("abc") is None


class TestBoolFromLegacy:
    def test_true_variants(self):
        for v in (True, 1, "S", "SI", "Y", "YES", "1", "T", "TRUE"):
            assert bool_from_legacy(v) is True

    def test_false_variants(self):
        for v in (False, 0, "", "N", "NO", "0", None):
            assert bool_from_legacy(v) is False


class TestNuivMapping:
    def test_consumer_final(self):
        assert NUIV_TO_CONDICION_IVA[1] == CondicionIvaEnum.consumidor_final

    def test_monotributo(self):
        assert NUIV_TO_CONDICION_IVA[2] == CondicionIvaEnum.monotributo

    def test_ri(self):
        assert NUIV_TO_CONDICION_IVA[3] == CondicionIvaEnum.responsable_inscripto

    def test_exento(self):
        assert NUIV_TO_CONDICION_IVA[5] == CondicionIvaEnum.exento


class TestUnidadMedidaFromLegacy:
    def test_unid_s_is_kg(self):
        assert unidad_medida_from_legacy("S") == UnidadMedidaEnum.kg

    def test_unid_n_is_unidad(self):
        assert unidad_medida_from_legacy("N") == UnidadMedidaEnum.unidad

    def test_heuristic_kg_from_desc(self):
        assert unidad_medida_from_legacy("", desc="Arroz 1 kg") == UnidadMedidaEnum.kg

    def test_heuristic_litro_from_desc(self):
        assert unidad_medida_from_legacy("", desc="Aceite 1 lt") == UnidadMedidaEnum.lt

    def test_default_is_unidad(self):
        assert unidad_medida_from_legacy("", desc="Cosa rara") == UnidadMedidaEnum.unidad

    def test_empty_input_is_unidad(self):
        assert unidad_medida_from_legacy(None) == UnidadMedidaEnum.unidad
