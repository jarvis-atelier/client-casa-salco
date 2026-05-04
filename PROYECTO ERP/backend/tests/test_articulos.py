"""Tests de CRUD y búsqueda de artículos."""
from __future__ import annotations

from faker import Faker

fake = Faker("es_AR")


def _create_articulo(client, token, auth_header, **overrides):
    payload = {
        "codigo": overrides.get("codigo", f"ART{fake.unique.random_int(100, 99999)}"),
        "descripcion": overrides.get("descripcion", fake.catch_phrase()),
        "codigo_barras": overrides.get("codigo_barras"),
        "unidad_medida": "unidad",
        "costo": "10.00",
        "pvp_base": "15.00",
    }
    r = client.post(
        "/api/v1/articulos", headers=auth_header(token), json=payload
    )
    assert r.status_code == 201, r.get_json()
    return r.get_json()


def test_crud_articulo(client, admin_token, auth_header):
    art = _create_articulo(
        client, admin_token, auth_header,
        codigo="A001", descripcion="Arroz Gallo 1kg", codigo_barras="7790001",
    )
    assert art["codigo"] == "A001"

    # list paginada
    r = client.get("/api/v1/articulos?page=1&per_page=10", headers=auth_header(admin_token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["total"] == 1
    assert body["items"][0]["codigo"] == "A001"

    # get
    r = client.get(f"/api/v1/articulos/{art['id']}", headers=auth_header(admin_token))
    assert r.status_code == 200

    # patch
    r = client.patch(
        f"/api/v1/articulos/{art['id']}",
        headers=auth_header(admin_token),
        json={"descripcion": "Arroz Gallo Oro 1kg"},
    )
    assert r.status_code == 200
    assert r.get_json()["descripcion"] == "Arroz Gallo Oro 1kg"

    # delete soft
    r = client.delete(f"/api/v1/articulos/{art['id']}", headers=auth_header(admin_token))
    assert r.status_code == 204

    r = client.get("/api/v1/articulos", headers=auth_header(admin_token))
    assert r.get_json()["total"] == 0


def test_articulo_busqueda(client, admin_token, auth_header):
    _create_articulo(
        client, admin_token, auth_header, codigo="A001", descripcion="Arroz Gallo"
    )
    _create_articulo(
        client, admin_token, auth_header, codigo="A002", descripcion="Fideos Molto"
    )
    _create_articulo(
        client, admin_token, auth_header, codigo="A003", descripcion="Arroz Lucchetti"
    )

    r = client.get("/api/v1/articulos?q=arroz", headers=auth_header(admin_token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["total"] == 2
    codigos = {i["codigo"] for i in body["items"]}
    assert codigos == {"A001", "A003"}


def test_articulo_paginacion(client, admin_token, auth_header):
    for i in range(12):
        _create_articulo(client, admin_token, auth_header, codigo=f"B{i:03d}")

    r = client.get("/api/v1/articulos?page=1&per_page=5", headers=auth_header(admin_token))
    body = r.get_json()
    assert body["total"] == 12
    assert body["pages"] == 3
    assert body["per_page"] == 5
    assert len(body["items"]) == 5


def test_articulo_codigo_duplicado(client, admin_token, auth_header):
    _create_articulo(client, admin_token, auth_header, codigo="X001")
    r = client.post(
        "/api/v1/articulos",
        headers=auth_header(admin_token),
        json={
            "codigo": "X001",
            "descripcion": "Duplicado",
            "unidad_medida": "unidad",
            "costo": "10",
            "pvp_base": "15",
        },
    )
    assert r.status_code == 409


def test_cajero_no_puede_crear_articulo(client, cajero_token, auth_header):
    r = client.post(
        "/api/v1/articulos",
        headers=auth_header(cajero_token),
        json={
            "codigo": "X001",
            "descripcion": "Should not",
            "unidad_medida": "unidad",
            "costo": "10",
            "pvp_base": "15",
        },
    )
    assert r.status_code == 403
