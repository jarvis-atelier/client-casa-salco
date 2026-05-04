"""Tests del endpoint /api/v1/comercio (singleton)."""
from __future__ import annotations


def test_get_comercio_creates_default_when_missing(client, admin_token, auth_header):
    r = client.get("/api/v1/comercio", headers=auth_header(admin_token))
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["id"] == 1
    assert body["razon_social"] == ""
    assert body["cuit"] == ""
    assert body["condicion_iva"] == ""


def test_patch_comercio_admin_ok(client, admin_token, auth_header):
    payload = {
        "razon_social": "Castulo SA",
        "cuit": "30-12345678-9",
        "condicion_iva": "Responsable Inscripto",
        "domicilio": "Av. San Martín 1200",
        "localidad": "Río Cuarto",
        "provincia": "Córdoba",
        "telefono": "0358-4636700",
        "email": "info@castulo.com",
        "iibb": "900-123456",
        "inicio_actividades": "2010-01-01",
        "pie_ticket": "Gracias por su compra",
    }
    r = client.patch(
        "/api/v1/comercio",
        json=payload,
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["razon_social"] == "Castulo SA"
    assert body["cuit"] == "30-12345678-9"
    assert body["condicion_iva"] == "Responsable Inscripto"
    assert body["pie_ticket"] == "Gracias por su compra"

    # GET refleja los cambios
    r2 = client.get("/api/v1/comercio", headers=auth_header(admin_token))
    assert r2.status_code == 200
    assert r2.get_json()["razon_social"] == "Castulo SA"


def test_patch_comercio_cajero_forbidden(client, cajero_token, auth_header):
    r = client.patch(
        "/api/v1/comercio",
        json={"razon_social": "X"},
        headers=auth_header(cajero_token),
    )
    assert r.status_code == 403


def test_get_comercio_cajero_ok(client, cajero_token, auth_header):
    # Cajeros pueden leer (ticket muestra los datos al imprimir).
    r = client.get("/api/v1/comercio", headers=auth_header(cajero_token))
    assert r.status_code == 200


def test_patch_comercio_invalid_cuit(client, admin_token, auth_header):
    r = client.patch(
        "/api/v1/comercio",
        json={"cuit": "no-cuit"},
        headers=auth_header(admin_token),
    )
    assert r.status_code == 422


def test_patch_comercio_cuit_with_or_without_dashes(client, admin_token, auth_header):
    r = client.patch(
        "/api/v1/comercio",
        json={"cuit": "30123456789"},
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    assert r.get_json()["cuit"] == "30123456789"
