"""Tests de CRUD de sucursales + áreas."""
from __future__ import annotations


def test_crud_sucursal_flow(client, admin_token, auth_header):
    # crear
    r = client.post(
        "/api/v1/sucursales",
        headers=auth_header(admin_token),
        json={"codigo": "SUC01", "nombre": "Central", "ciudad": "Rio Cuarto"},
    )
    assert r.status_code == 201
    suc = r.get_json()
    assert suc["codigo"] == "SUC01"

    # listar
    r = client.get("/api/v1/sucursales", headers=auth_header(admin_token))
    assert r.status_code == 200
    assert len(r.get_json()) == 1

    # get by id
    r = client.get(f"/api/v1/sucursales/{suc['id']}", headers=auth_header(admin_token))
    assert r.status_code == 200
    assert r.get_json()["id"] == suc["id"]

    # patch
    r = client.patch(
        f"/api/v1/sucursales/{suc['id']}",
        headers=auth_header(admin_token),
        json={"nombre": "Central Rio Cuarto"},
    )
    assert r.status_code == 200
    assert r.get_json()["nombre"] == "Central Rio Cuarto"

    # delete soft
    r = client.delete(f"/api/v1/sucursales/{suc['id']}", headers=auth_header(admin_token))
    assert r.status_code == 204

    # ya no aparece
    r = client.get("/api/v1/sucursales", headers=auth_header(admin_token))
    assert len(r.get_json()) == 0


def test_sucursal_codigo_duplicate(client, admin_token, auth_header):
    client.post(
        "/api/v1/sucursales",
        headers=auth_header(admin_token),
        json={"codigo": "SUC01", "nombre": "Uno"},
    )
    r = client.post(
        "/api/v1/sucursales",
        headers=auth_header(admin_token),
        json={"codigo": "SUC01", "nombre": "Otro"},
    )
    assert r.status_code == 409


def test_cajero_no_puede_crear(client, cajero_token, auth_header):
    r = client.post(
        "/api/v1/sucursales",
        headers=auth_header(cajero_token),
        json={"codigo": "SUC01", "nombre": "Central"},
    )
    assert r.status_code == 403


def test_areas_flow(client, admin_token, auth_header):
    r = client.post(
        "/api/v1/sucursales",
        headers=auth_header(admin_token),
        json={"codigo": "SUC01", "nombre": "Central"},
    )
    suc_id = r.get_json()["id"]

    r = client.post(
        f"/api/v1/sucursales/{suc_id}/areas",
        headers=auth_header(admin_token),
        json={"codigo": "COM", "nombre": "Comestibles", "orden": 10},
    )
    assert r.status_code == 201

    r = client.get(f"/api/v1/sucursales/{suc_id}/areas", headers=auth_header(admin_token))
    assert r.status_code == 200
    rows = r.get_json()
    assert len(rows) == 1
    assert rows[0]["codigo"] == "COM"
