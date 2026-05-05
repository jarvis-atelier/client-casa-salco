"""Unit tests for `etl.xls.mappers._tipo_heuristic.assign_tipos`.

Covers spec scenarios S3-S6 + S11 + B1 edge cases (cantidad=0, invalid).
Pure function, no DB / IO required.
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.articulo_codigo import TipoCodigoArticuloEnum
from etl.xls.mappers._tipo_heuristic import assign_tipos


def _row(codigo_articulo: str, codigo: str, cantidad) -> dict:
    """Helper: minimal row dict the heuristic operates on."""
    return {
        "codigo_articulo": codigo_articulo,
        "codigo": codigo,
        "cantidad": cantidad,
    }


class TestSingleRowGroups:
    def test_single_row_cantidad_1_principal(self):
        rows = [_row("A1", "C-1", Decimal("1"))]
        out = assign_tipos(rows)
        assert out[0]["tipo"] is TipoCodigoArticuloEnum.principal

    def test_single_row_cantidad_gt1_empaquetado(self):
        # No cantidad=1 in group -> first (only) row forced principal.
        rows = [_row("A1", "C-12", Decimal("12"))]
        out = assign_tipos(rows)
        assert out[0]["tipo"] is TipoCodigoArticuloEnum.principal


class TestMultipleRowGroups:
    def test_multiple_cantidad_1_first_wins(self):
        # First cantidad=1 (input order) -> principal; the rest -> alterno.
        rows = [
            _row("A1", "C-A", Decimal("1")),
            _row("A1", "C-B", Decimal("1")),
            _row("A1", "C-C", Decimal("1")),
        ]
        out = assign_tipos(rows)
        assert out[0]["tipo"] is TipoCodigoArticuloEnum.principal
        assert out[1]["tipo"] is TipoCodigoArticuloEnum.alterno
        assert out[2]["tipo"] is TipoCodigoArticuloEnum.alterno

    def test_no_cantidad_1_first_default_principal(self):
        # No cantidad=1 anywhere -> first row forced principal, rest empaquetado.
        rows = [
            _row("A1", "C-A", Decimal("6")),
            _row("A1", "C-B", Decimal("12")),
            _row("A1", "C-C", Decimal("24")),
        ]
        out = assign_tipos(rows)
        assert out[0]["tipo"] is TipoCodigoArticuloEnum.principal
        assert out[1]["tipo"] is TipoCodigoArticuloEnum.empaquetado
        assert out[2]["tipo"] is TipoCodigoArticuloEnum.empaquetado

    def test_mixed_cantidad_1_and_gt1(self):
        # Mix: first cantidad=1 -> principal; cantidad>1 -> empaquetado;
        # second cantidad=1 -> alterno.
        rows = [
            _row("A1", "C-1", Decimal("1")),
            _row("A1", "C-12", Decimal("12")),
            _row("A1", "C-A", Decimal("1")),
            _row("A1", "C-6", Decimal("6")),
        ]
        out = assign_tipos(rows)
        assert out[0]["tipo"] is TipoCodigoArticuloEnum.principal
        assert out[1]["tipo"] is TipoCodigoArticuloEnum.empaquetado
        assert out[2]["tipo"] is TipoCodigoArticuloEnum.alterno
        assert out[3]["tipo"] is TipoCodigoArticuloEnum.empaquetado


class TestEdgeCases:
    def test_cantidad_zero_coerces_to_unit(self):
        # B1 audit: 19 rows with cantidad=0 -> treated as single-unit row.
        # First zero-row in group (no cantidad=1) -> principal via unit branch.
        rows = [
            _row("A1", "C-0", Decimal("0")),
            _row("A1", "C-12", Decimal("12")),
        ]
        out = assign_tipos(rows)
        assert out[0]["tipo"] is TipoCodigoArticuloEnum.principal
        assert out[1]["tipo"] is TipoCodigoArticuloEnum.empaquetado

    def test_cantidad_zero_with_explicit_one_zero_is_alterno(self):
        # cantidad=1 row first, cantidad=0 second -> 0 is treated as unit -> alterno.
        rows = [
            _row("A1", "C-1", Decimal("1")),
            _row("A1", "C-0", Decimal("0")),
        ]
        out = assign_tipos(rows)
        assert out[0]["tipo"] is TipoCodigoArticuloEnum.principal
        assert out[1]["tipo"] is TipoCodigoArticuloEnum.alterno

    def test_cantidad_negative_invalid_alterno(self):
        # Negative cantidad is invalid; group has a valid cantidad=1 first row.
        rows = [
            _row("A1", "C-1", Decimal("1")),
            _row("A1", "C-NEG", Decimal("-5")),
        ]
        out = assign_tipos(rows)
        assert out[0]["tipo"] is TipoCodigoArticuloEnum.principal
        assert out[1]["tipo"] is TipoCodigoArticuloEnum.alterno

    def test_cantidad_none_invalid_alterno(self):
        rows = [
            _row("A1", "C-1", Decimal("1")),
            _row("A1", "C-NONE", None),
        ]
        out = assign_tipos(rows)
        assert out[0]["tipo"] is TipoCodigoArticuloEnum.principal
        assert out[1]["tipo"] is TipoCodigoArticuloEnum.alterno

    def test_cantidad_decimal_15_valid(self):
        # Fractional cantidad (B1 found 217 such rows). cantidad=1.5 != 1 and > 0
        # -> treated as empaquetado in a group with cantidad=1.
        rows = [
            _row("A1", "C-1", Decimal("1")),
            _row("A1", "C-15", Decimal("1.5")),
        ]
        out = assign_tipos(rows)
        assert out[0]["tipo"] is TipoCodigoArticuloEnum.principal
        assert out[1]["tipo"] is TipoCodigoArticuloEnum.empaquetado

    def test_all_invalid_first_forced_principal(self):
        # Whole group invalid -> first forced principal, rest alterno.
        rows = [
            _row("A1", "C-A", None),
            _row("A1", "C-B", Decimal("-3")),
            _row("A1", "C-C", None),
        ]
        out = assign_tipos(rows)
        assert out[0]["tipo"] is TipoCodigoArticuloEnum.principal
        assert out[1]["tipo"] is TipoCodigoArticuloEnum.alterno
        assert out[2]["tipo"] is TipoCodigoArticuloEnum.alterno


class TestContract:
    def test_input_order_preserved(self):
        # The function must NOT reorder rows. Verify by checking codes per index.
        rows = [
            _row("A1", "C-1", Decimal("1")),
            _row("A2", "C-2", Decimal("1")),
            _row("A1", "C-12", Decimal("12")),
            _row("A2", "C-6", Decimal("6")),
        ]
        codigos_before = [r["codigo"] for r in rows]
        out = assign_tipos(rows)
        codigos_after = [r["codigo"] for r in out]
        assert codigos_before == codigos_after

    def test_returns_same_list_reference(self):
        rows: list[dict] = [_row("A1", "C-1", Decimal("1"))]
        out = assign_tipos(rows)
        assert out is rows
        # And rows were mutated in place.
        assert "tipo" in rows[0]

    def test_multi_group_independence(self):
        # Two distinct codigo_articulo groups must be assigned independently.
        rows = [
            _row("A1", "C-1A", Decimal("1")),
            _row("A2", "C-2A", Decimal("12")),  # group A2 has no cantidad=1
            _row("A1", "C-1B", Decimal("12")),
            _row("A2", "C-2B", Decimal("24")),
        ]
        out = assign_tipos(rows)
        # A1 group: cantidad=1 first -> principal; cantidad=12 -> empaquetado.
        assert out[0]["tipo"] is TipoCodigoArticuloEnum.principal
        assert out[2]["tipo"] is TipoCodigoArticuloEnum.empaquetado
        # A2 group: no cantidad=1 -> first forced principal; rest empaquetado.
        assert out[1]["tipo"] is TipoCodigoArticuloEnum.principal
        assert out[3]["tipo"] is TipoCodigoArticuloEnum.empaquetado
