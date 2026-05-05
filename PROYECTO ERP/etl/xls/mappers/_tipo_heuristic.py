"""Pure heuristic to assign `tipo` to EMPAQUETADOS rows.

Decisions documented in `casa-salco/cliente-rf07-simplificado` and design #559.
Single-file edit point if cliente changes the rule.

Rules (per group keyed by `codigo_articulo`, preserving xls input order):

- Group has >=1 row with cantidad == 1:
  * First (input order) cantidad=1 row -> tipo='principal'.
  * Other cantidad=1 rows               -> tipo='alterno'.
  * cantidad > 1 rows                   -> tipo='empaquetado'.
  * Invalid cantidad rows (None / negative / non-numeric) -> tipo='alterno'.

- Group has NO cantidad == 1:
  * First row (input order) -> tipo='principal' (forced default).
  * Remaining rows with valid cantidad > 1 -> tipo='empaquetado'.
  * Remaining rows with invalid cantidad   -> tipo='alterno'.

Edges:
- cantidad == 0 is coerced to a single-unit row (B1 audit found 19 such rows).
- cantidad None / negative / non-numeric is invalid -> tipo='alterno'
  (unless it is the forced first row of an all-invalid group, then 'principal').
"""
from __future__ import annotations

from collections import defaultdict
from decimal import Decimal, InvalidOperation

from app.models.articulo_codigo import TipoCodigoArticuloEnum

ONE = Decimal("1")
ZERO = Decimal("0")


def _to_decimal(value) -> Decimal | None:
    """Best-effort conversion to Decimal. Returns None on failure / None input."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return None


def _is_unit_cantidad(cantidad) -> bool:
    """True iff the row should be treated as a single-unit code.

    Includes cantidad == 1 and the cantidad == 0 edge (B1: 19 rows -> coerced to 1).
    Negative / None / non-numeric is NOT a unit.
    """
    c = _to_decimal(cantidad)
    if c is None:
        return False
    if c == ONE:
        return True
    if c == ZERO:
        # B1 audit: 19 rows with cantidad=0 -> coerce to 1 (single unit).
        return True
    return False


def _is_valid_cantidad(cantidad) -> bool:
    """True iff cantidad parses to a strictly positive Decimal."""
    c = _to_decimal(cantidad)
    if c is None:
        return False
    return c > ZERO


def assign_tipos(rows: list[dict]) -> list[dict]:
    """Assign `tipo` field to each row in-place (returns the same list reference).

    Args:
        rows: list[dict] with at least keys 'codigo_articulo' and 'cantidad'.
              Order is the canonical xls read order and is preserved.

    Returns:
        The SAME list reference, with each dict updated to include 'tipo'
        as a `TipoCodigoArticuloEnum` member.
    """
    by_articulo: dict = defaultdict(list)
    for r in rows:
        by_articulo[r["codigo_articulo"]].append(r)

    for _codigo_articulo, group in by_articulo.items():
        units = [r for r in group if _is_unit_cantidad(r["cantidad"])]

        if units:
            first_unit_id = id(units[0])
            for r in group:
                if _is_unit_cantidad(r["cantidad"]):
                    r["tipo"] = (
                        TipoCodigoArticuloEnum.principal
                        if id(r) == first_unit_id
                        else TipoCodigoArticuloEnum.alterno
                    )
                elif _is_valid_cantidad(r["cantidad"]):
                    # cantidad > 1 valid -> empaquetado
                    r["tipo"] = TipoCodigoArticuloEnum.empaquetado
                else:
                    # invalid (None / negative / non-numeric) -> alterno
                    r["tipo"] = TipoCodigoArticuloEnum.alterno
        else:
            # No cantidad=1 in group -> first row forced as principal.
            for i, r in enumerate(group):
                if i == 0:
                    r["tipo"] = TipoCodigoArticuloEnum.principal
                elif _is_valid_cantidad(r["cantidad"]):
                    r["tipo"] = TipoCodigoArticuloEnum.empaquetado
                else:
                    r["tipo"] = TipoCodigoArticuloEnum.alterno

    return rows
