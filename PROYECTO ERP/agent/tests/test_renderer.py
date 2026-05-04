"""Tests for the ticket renderer (pure functions)."""
from __future__ import annotations

from jarvis_agent.ticket.renderer import render_ticket


def test_basic_ticket_has_razon_social_in_header(factura_a_payload):
    out = render_ticket(factura_a_payload)
    text = "\n".join(out.lines)
    assert "CASTULO SA" in text
    # Should contain ESC/POS init bytes
    assert out.escpos_bytes.startswith(b"\x1b@")
    # Should end with cut command
    assert out.escpos_bytes.endswith(b"\x1d\x56\x42\x00")


def test_factura_a_header_shows_letter(factura_a_payload):
    out = render_ticket(factura_a_payload)
    text = "\n".join(out.lines)
    assert "FACTURA A" in text
    # Numero formateado punto-venta-numero
    assert "0001-00000042" in text


def test_kg_item_shows_decimal_and_unit(kg_item_payload):
    out = render_ticket(kg_item_payload)
    text = "\n".join(out.lines)
    # "2.5 kg" because trailing zeros are stripped
    assert "2.5 kg" in text or "2.500 kg" in text


def test_qr_present_when_afip_present(factura_a_payload):
    out = render_ticket(factura_a_payload)
    assert out.qr_png is not None
    assert out.qr_png.startswith(b"\x89PNG")
    # ESC/POS bytes must include the raster image command (GS v 0)
    assert b"\x1dv0\x00" in out.escpos_bytes
    # Plain-text marker [QR AFIP] removed in escpos but present in lines
    assert any("[QR AFIP]" in line for line in out.lines)


def test_no_qr_when_afip_missing(sample_no_afip_payload=None):
    from tests.conftest import sample_payload

    out = render_ticket(sample_payload(afip=None))
    assert out.qr_png is None
    assert b"\x1dv0\x00" not in out.escpos_bytes


def test_paper_width_58mm_yields_32_chars():
    from tests.conftest import sample_payload

    out = render_ticket(sample_payload(ancho_papel_mm=58))
    assert out.width_chars == 32
    # All non-empty lines must be <= width
    for line in out.lines:
        assert len(line) <= 32


def test_paper_width_80mm_yields_48_chars():
    from tests.conftest import sample_payload

    out = render_ticket(sample_payload(ancho_papel_mm=80))
    assert out.width_chars == 48


def test_total_line_includes_money(factura_a_payload):
    out = render_ticket(factura_a_payload)
    total_lines = [line for line in out.lines if line.lstrip().startswith("TOTAL")]
    assert len(total_lines) >= 1
    assert "2662.00" in total_lines[0]


def test_metadata_includes_numero_and_total(factura_a_payload):
    out = render_ticket(factura_a_payload)
    assert out.metadata["tipo"] == "factura_a"
    assert out.metadata["numero"] == "0001-00000042"
    assert out.metadata["total"] == "2662.00"


def test_pago_efectivo_appears_in_lines():
    from tests.conftest import sample_payload

    out = render_ticket(sample_payload())
    text = "\n".join(out.lines).lower()
    assert "efectivo" in text


def test_special_chars_encoded_safely_in_escpos():
    """Argentine text with accents must not crash the encoder."""
    from decimal import Decimal

    from jarvis_agent.ticket.renderer import (
        Comercio,
        ComprobantePayload,
        IvaDesglose,
        ItemPayload,
        SucursalPayload,
        TicketPayload,
        TotalesPayload,
    )
    from datetime import datetime

    p = TicketPayload(
        tipo="ticket",
        comercio=Comercio(razon_social="Almacén Doña Ñoña", cuit="30-1-2"),
        sucursal=SucursalPayload(codigo="X", nombre="Sucursal Niño", punto_venta=1),
        comprobante=ComprobantePayload(
            tipo_letra="X",
            numero=1,
            fecha=datetime(2026, 1, 1, 12, 0),
            razon_social_receptor="José Pérez",
        ),
        items=[
            ItemPayload(
                codigo="X",
                descripcion="Áéíóú ñ ° ·",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100"),
                subtotal=Decimal("100"),
            )
        ],
        totales=TotalesPayload(
            subtotal=Decimal("100"),
            total_iva=Decimal("21"),
            iva_desglosado=[
                IvaDesglose(alic=Decimal("21"), base=Decimal("100"), iva=Decimal("21"))
            ],
            total=Decimal("121"),
        ),
    )
    out = render_ticket(p)
    # Bytes are valid (no exception), and non-empty
    assert len(out.escpos_bytes) > 100
