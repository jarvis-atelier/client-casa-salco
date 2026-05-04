"""Tests del endpoint POST /api/v1/facturas/<id>/emitir-cae.

Estos tests crean Factura directamente via ORM (no dependen del endpoint de
creacion de facturas de 2.1). Si el modelo Factura aun no existe (imports
fallan), los tests se skippean automaticamente.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

# Si Factura todavia no existe (fase 2.1 no termino), skippear todo el modulo.
try:
    from app.models.factura import EstadoComprobanteEnum, Factura, TipoComprobanteEnum
    from app.models.sucursal import Sucursal

    FACTURA_DISPONIBLE = True
except ImportError:  # pragma: no cover
    FACTURA_DISPONIBLE = False

pytestmark = pytest.mark.skipif(
    not FACTURA_DISPONIBLE,
    reason="modelo Factura (fase 2.1) aun no disponible",
)


# -------------------------------------------------------------------- fixtures


@pytest.fixture
def sucursal(db):
    suc = Sucursal(codigo="TEST01", nombre="Sucursal Test", activa=True)
    db.session.add(suc)
    db.session.commit()
    return suc


@pytest.fixture
def factura_b(db, sucursal, admin_user):
    """Factura B consumidor final, total 121.00, IVA 21.00."""
    f = Factura(
        sucursal_id=sucursal.id,
        punto_venta=1,
        tipo=TipoComprobanteEnum.factura_b,
        numero=1,
        fecha=datetime.now(UTC),
        cajero_id=admin_user.id,
        estado=EstadoComprobanteEnum.emitida,
        subtotal=Decimal("100.00"),
        total_iva=Decimal("21.00"),
        total_descuento=Decimal("0"),
        total=Decimal("121.00"),
        moneda="ARS",
        cotizacion=Decimal("1"),
    )
    db.session.add(f)
    db.session.commit()
    return f


@pytest.fixture
def factura_remito(db, sucursal, admin_user):
    """Factura tipo remito — NO requiere CAE."""
    f = Factura(
        sucursal_id=sucursal.id,
        punto_venta=1,
        tipo=TipoComprobanteEnum.remito,
        numero=1,
        fecha=datetime.now(UTC),
        cajero_id=admin_user.id,
        estado=EstadoComprobanteEnum.emitida,
        subtotal=Decimal("100.00"),
        total_iva=Decimal("0"),
        total_descuento=Decimal("0"),
        total=Decimal("100.00"),
    )
    db.session.add(f)
    db.session.commit()
    return f


# --------------------------------------------------------------------- tests


def test_emitir_cae_ok(client, admin_token, auth_header, factura_b):
    r = client.post(
        f"/api/v1/facturas/{factura_b.id}/emitir-cae",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 201, r.get_json()
    body = r.get_json()

    assert body["factura_id"] == factura_b.id
    assert len(body["cae"]) == 14
    assert body["cae"].isdigit()
    assert body["resultado"] == "A"
    assert body["reproceso"] == "N"
    assert body["tipo_afip"] == 6  # Factura B
    assert body["proveedor"] == "mock"
    assert body["qr_url"].startswith("https://www.afip.gob.ar/fe/qr/?p=")
    assert "fecha_vencimiento" in body


def test_emitir_cae_actualiza_factura(client, admin_token, auth_header, db, factura_b):
    r = client.post(
        f"/api/v1/facturas/{factura_b.id}/emitir-cae",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 201

    # Re-leer factura desde DB — debe tener cae + cae_vencimiento + qr_afip.
    db.session.expire_all()
    refreshed = db.session.get(Factura, factura_b.id)
    assert refreshed.cae is not None
    assert len(refreshed.cae) == 14
    assert refreshed.cae_vencimiento is not None
    assert refreshed.qr_afip is not None
    assert refreshed.qr_afip.startswith("https://www.afip.gob.ar/fe/qr/")


def test_emitir_cae_persiste_registro_cae(client, admin_token, auth_header, db, factura_b):
    from app.models.cae import Cae

    r = client.post(
        f"/api/v1/facturas/{factura_b.id}/emitir-cae",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 201

    cae_row = db.session.query(Cae).filter(Cae.factura_id == factura_b.id).first()
    assert cae_row is not None
    assert cae_row.proveedor == "mock"
    assert cae_row.resultado == "A"
    assert cae_row.tipo_afip == 6
    assert cae_row.punto_venta == 1
    assert cae_row.qr_url.startswith("https://www.afip.gob.ar/fe/qr/")


def test_emitir_cae_duplicado_409(client, admin_token, auth_header, factura_b):
    r1 = client.post(
        f"/api/v1/facturas/{factura_b.id}/emitir-cae",
        headers=auth_header(admin_token),
    )
    assert r1.status_code == 201

    r2 = client.post(
        f"/api/v1/facturas/{factura_b.id}/emitir-cae",
        headers=auth_header(admin_token),
    )
    assert r2.status_code == 409
    body = r2.get_json()
    assert body["code"] == "cae_ya_emitido"
    assert "details" in body
    assert body["details"]["cae"] == r1.get_json()["cae"]


def test_emitir_cae_factura_inexistente_404(client, admin_token, auth_header):
    r = client.post(
        "/api/v1/facturas/999999/emitir-cae",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 404


def test_emitir_cae_remito_rechaza(client, admin_token, auth_header, factura_remito):
    r = client.post(
        f"/api/v1/facturas/{factura_remito.id}/emitir-cae",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 400
    body = r.get_json()
    assert body["code"] == "tipo_sin_cae"


def test_emitir_cae_requiere_jwt(client, factura_b):
    r = client.post(f"/api/v1/facturas/{factura_b.id}/emitir-cae")
    assert r.status_code == 401


def test_emitir_cae_cajero_rechazado(client, cajero_token, auth_header, factura_b):
    """RBAC: cajero no puede emitir CAE (solo admin/supervisor)."""
    r = client.post(
        f"/api/v1/facturas/{factura_b.id}/emitir-cae",
        headers=auth_header(cajero_token),
    )
    assert r.status_code == 403


def test_emitir_cae_supervisor_ok(client, supervisor_token, auth_header, factura_b):
    r = client.post(
        f"/api/v1/facturas/{factura_b.id}/emitir-cae",
        headers=auth_header(supervisor_token),
    )
    assert r.status_code == 201
