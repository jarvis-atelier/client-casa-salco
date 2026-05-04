"""HTTP-level integration tests."""
from __future__ import annotations

from tests.conftest import sample_payload_dict


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.get_json()["ok"] is True


def test_status_mock(client):
    r = client.get("/status")
    assert r.status_code == 200
    body = r.get_json()
    assert body["driver"] == "mock"
    assert body["status"] == "ready"
    assert body["online"] is True


def test_print_ticket_ok(client):
    payload = sample_payload_dict()
    r = client.post("/print/ticket", json=payload)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["printed"] is True
    assert "preview_url" in body
    assert body["preview_url"].startswith("/preview/")
    assert body["driver"] == "mock"
    assert body["metadata"]["tipo"] == "ticket"


def test_print_ticket_factura_a_with_cae(client):
    from datetime import date

    payload = sample_payload_dict(tipo="factura_a")
    payload["comprobante"]["tipo_letra"] = "A"
    payload["afip"] = {
        "cae": "30686532297689",
        "vencimiento": str(date(2026, 5, 4)),
        "qr_url": "https://www.afip.gob.ar/fe/qr/?p=eyJ2ZXIiOjF9",
    }
    r = client.post("/print/ticket", json=payload)
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["printed"] is True


def test_print_ticket_invalid_payload_returns_422(client):
    r = client.post("/print/ticket", json={"tipo": "ticket"})
    assert r.status_code == 422
    body = r.get_json()
    assert body["printed"] is False
    assert "details" in body


def test_print_ticket_missing_body_returns_400(client):
    r = client.post("/print/ticket", data="not json", content_type="application/json")
    assert r.status_code == 400


def test_preview_returns_pdf(client):
    payload = sample_payload_dict()
    r = client.post("/print/ticket", json=payload)
    pid = r.get_json()["preview_id"]

    r2 = client.get(f"/preview/{pid}")
    assert r2.status_code == 200
    assert r2.mimetype == "application/pdf"
    assert r2.data[:4] == b"%PDF"


def test_preview_unknown_returns_404(client):
    r = client.get("/preview/does-not-exist")
    assert r.status_code == 404


def test_cors_headers_for_frontend_origin(client):
    """Frontend at :5173 must be allowed."""
    r = client.get("/status", headers={"Origin": "http://localhost:5173"})
    assert r.headers.get("Access-Control-Allow-Origin") == "http://localhost:5173"
