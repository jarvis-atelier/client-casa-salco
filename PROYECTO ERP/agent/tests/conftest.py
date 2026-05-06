"""Shared test fixtures."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from jarvis_agent.app import create_app
from jarvis_agent.config import Settings, reset_settings_cache
from jarvis_agent.printer.mock import MockPrinter
from jarvis_agent.scale.factory import reset_scale_cache
from jarvis_agent.scale.mock import MockScale
from jarvis_agent.ticket.renderer import (
    AfipPayload,
    Comercio,
    ComprobantePayload,
    IvaDesglose,
    ItemPayload,
    PagoPayload,
    SucursalPayload,
    TicketPayload,
    TotalesPayload,
)


@pytest.fixture(autouse=True)
def _reset_settings():
    reset_settings_cache()
    reset_scale_cache()
    yield
    reset_settings_cache()
    reset_scale_cache()


@pytest.fixture()
def tmp_output(tmp_path: Path) -> Path:
    out = tmp_path / "out"
    out.mkdir()
    return out


@pytest.fixture()
def mock_printer(tmp_output: Path) -> MockPrinter:
    return MockPrinter(output_dir=tmp_output)


@pytest.fixture()
def settings(tmp_output: Path) -> Settings:
    return Settings(
        PRINTER_MODE="mock",
        OUTPUT_DIR=str(tmp_output),
    )


@pytest.fixture()
def mock_scale() -> MockScale:
    # Seeded so test assertions on bounds are stable across runs.
    return MockScale(seed=42)


@pytest.fixture()
def app(settings: Settings, mock_printer: MockPrinter, mock_scale: MockScale):
    app = create_app(
        settings,
        printer_driver=mock_printer,
        scale_driver=mock_scale,
    )
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Sample payloads
# ---------------------------------------------------------------------------


def sample_payload(**overrides) -> TicketPayload:
    """Return a baseline ticket payload — overridable for specific tests."""
    base = dict(
        tipo="ticket",
        comercio=Comercio(
            razon_social="CASA SALCO SA",
            cuit="30-12345678-9",
            direccion="Av. San Martin 1200, Rio Cuarto",
            telefono="0358-4636700",
            iibb="900-123456",
            inicio_actividades="2010-01-01",
        ),
        sucursal=SucursalPayload(codigo="SUC01", nombre="CASA SALCO Centro", punto_venta=1),
        comprobante=ComprobantePayload(
            tipo_letra="X",
            numero=12,
            fecha=datetime(2026, 4, 24, 18, 30),
            tipo_doc_receptor=99,
            nro_doc_receptor="0",
            razon_social_receptor="Consumidor Final",
            condicion_iva_receptor="Consumidor Final",
        ),
        items=[
            ItemPayload(
                codigo="ARRZ-001",
                descripcion="Arroz Marolio Largo Fino 1kg",
                cantidad=Decimal("2"),
                unidad="unidad",
                precio_unitario=Decimal("1100.00"),
                subtotal=Decimal("2200.00"),
                iva_porc=Decimal("21"),
            )
        ],
        totales=TotalesPayload(
            subtotal=Decimal("2200.00"),
            total_descuento=Decimal("0"),
            total_iva=Decimal("462.00"),
            iva_desglosado=[
                IvaDesglose(
                    alic=Decimal("21"), base=Decimal("2200.00"), iva=Decimal("462.00")
                )
            ],
            total=Decimal("2662.00"),
        ),
        pagos=[
            PagoPayload(medio="efectivo", monto=Decimal("2700.00")),
            PagoPayload(medio="vuelto", monto=Decimal("-38.00")),
        ],
        afip=None,
        cajero="Juan Perez",
        observacion=None,
        ancho_papel_mm=80,
    )
    base.update(overrides)
    return TicketPayload(**base)


def sample_payload_dict(**overrides) -> dict:
    """JSON-serializable dict version of sample_payload — for HTTP tests."""
    payload = sample_payload(**overrides)
    return payload.model_dump(mode="json")


@pytest.fixture()
def factura_a_payload() -> TicketPayload:
    return sample_payload(
        tipo="factura_a",
        comprobante=ComprobantePayload(
            tipo_letra="A",
            numero=42,
            fecha=datetime(2026, 4, 24, 18, 30),
            tipo_doc_receptor=80,
            nro_doc_receptor="20-12345678-3",
            razon_social_receptor="Distribuidora Norte SRL",
            condicion_iva_receptor="Responsable Inscripto",
        ),
        afip=AfipPayload(
            cae="30686532297689",
            vencimiento=date(2026, 5, 4),
            qr_url=(
                "https://www.afip.gob.ar/fe/qr/?p="
                "eyJ2ZXIiOjEsImZlY2hhIjoiMjAyNi0wNC0yNCIsImN1aXQiOjMwMTIzNDU2Nzg5fQ=="
            ),
        ),
    )


@pytest.fixture()
def kg_item_payload() -> TicketPayload:
    return sample_payload(
        items=[
            ItemPayload(
                codigo="QSO-PROV",
                descripcion="Queso Provoleta x kg",
                cantidad=Decimal("2.500"),
                unidad="kg",
                precio_unitario=Decimal("8200.00"),
                subtotal=Decimal("20500.00"),
                iva_porc=Decimal("21"),
            )
        ],
        totales=TotalesPayload(
            subtotal=Decimal("20500.00"),
            total_iva=Decimal("4305.00"),
            iva_desglosado=[
                IvaDesglose(
                    alic=Decimal("21"),
                    base=Decimal("20500.00"),
                    iva=Decimal("4305.00"),
                )
            ],
            total=Decimal("24805.00"),
        ),
    )
