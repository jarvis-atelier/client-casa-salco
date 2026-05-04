"""Pure-text ticket layout helpers — used both by the ESC/POS encoder and the
PDF mock renderer so they always show the same content.

The renderer keeps text monospaced and right-aligns prices. Width depends on
the paper:
- 58 mm  ->  32 chars
- 80 mm  ->  48 chars
"""
from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal


def width_for_paper_mm(mm: int) -> int:
    """Return char-width for a given paper width in mm.

    3NSTAR PRP-080 with default 12x24 dot font fits ~48 chars on 80mm and
    ~32 chars on 58mm. We snap to the closer of the two.
    """
    return 32 if mm <= 58 else 48


def hr(width: int, char: str = "-") -> str:
    return char * width


def center(text: str, width: int) -> str:
    text = text[:width]
    pad = max(0, (width - len(text)) // 2)
    return " " * pad + text


def two_cols(left: str, right: str, width: int) -> str:
    """Left-aligned + right-aligned in one line. Truncates left if needed."""
    right = right[:width]
    space = width - len(right)
    if space <= 1:
        return right.rjust(width)
    left = left[: max(0, space - 1)]
    return left + " " * (width - len(left) - len(right)) + right


def kv_line(key: str, value: str, width: int) -> str:
    return two_cols(key, value, width)


def fmt_money(value: Decimal | float | str | None) -> str:
    """Format AR money like 12.345,67 -> "$ 12345.67" (no thousands separator
    to avoid eating column width on narrow tickets)."""
    if value is None or value == "":
        return "$ 0.00"
    if isinstance(value, str):
        try:
            value = Decimal(value)
        except Exception:
            return f"$ {value}"
    if isinstance(value, float):
        value = Decimal(str(value))
    sign = "-" if value < 0 else ""
    return f"{sign}$ {abs(value):.2f}"


def fmt_qty(qty: Decimal | float | str | None, unidad: str | None = None) -> str:
    """Format quantity. Integers shown without trailing zeros; decimals up to 3."""
    if qty is None:
        return ""
    if isinstance(qty, str):
        qty = Decimal(qty)
    if isinstance(qty, float):
        qty = Decimal(str(qty))
    # Use 3 decimals only if non-integer
    if qty == qty.to_integral_value():
        text = f"{int(qty)}"
    else:
        text = f"{qty:.3f}".rstrip("0").rstrip(".")
    if unidad and unidad.lower() not in ("unidad", "u", "un"):
        text += f" {unidad}"
    return text


# Wrapping for long descriptions ----------------------------------------------


def wrap(text: str, width: int) -> Iterable[str]:
    """Naive word-wrap for ESC/POS — preserves word boundaries when possible."""
    if not text:
        yield ""
        return
    words = text.split(" ")
    line = ""
    for w in words:
        if not line:
            line = w[:width]
            continue
        if len(line) + 1 + len(w) <= width:
            line = f"{line} {w}"
        else:
            yield line
            line = w[:width]
    if line:
        yield line


# Headers per comprobante type ------------------------------------------------


COMPROBANTE_HEADERS: dict[str, str] = {
    "ticket": "TICKET",
    "factura_a": "FACTURA A",
    "factura_b": "FACTURA B",
    "factura_c": "FACTURA C",
    "nc_a": "NOTA DE CREDITO A",
    "nc_b": "NOTA DE CREDITO B",
    "nc_c": "NOTA DE CREDITO C",
    "remito": "REMITO",
    "presupuesto": "PRESUPUESTO",
    "comanda": "COMANDA",
}


def header_label(tipo: str, tipo_letra: str | None = None) -> str:
    """Return the big header line for the comprobante.

    `tipo_letra` overrides when provided (e.g. "B") so the receipt shows
    "FACTURA B" cleanly.
    """
    if tipo_letra:
        if tipo.startswith("nc_"):
            return f"NOTA DE CREDITO {tipo_letra}"
        if tipo.startswith("factura_") or tipo == "ticket":
            return (
                f"FACTURA {tipo_letra}"
                if tipo.startswith("factura_")
                else f"TICKET {tipo_letra}".strip()
            )
    return COMPROBANTE_HEADERS.get(tipo, tipo.upper())
