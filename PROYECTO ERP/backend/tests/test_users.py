"""Tests de /api/v1/auth/users (admin-only)."""
from __future__ import annotations


def test_list_users_admin_ok(client, admin_token, cajero_token, auth_header):
    # cajero_token genera al cajero_user fixture y al admin
    r = client.get("/api/v1/auth/users", headers=auth_header(admin_token))
    assert r.status_code == 200
    rows = r.get_json()
    assert isinstance(rows, list)
    assert len(rows) >= 1
    emails = [u["email"] for u in rows]
    assert "admin@test.example" in emails


def test_list_users_cajero_forbidden(client, cajero_token, auth_header):
    r = client.get("/api/v1/auth/users", headers=auth_header(cajero_token))
    assert r.status_code == 403


def test_register_then_update_user(client, admin_token, auth_header):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "newuser@test.example",
            "password": "secret123",
            "nombre": "Nuevo",
            "rol": "cajero",
        },
        headers=auth_header(admin_token),
    )
    assert r.status_code == 201
    user_id = r.get_json()["id"]

    r2 = client.patch(
        f"/api/v1/auth/users/{user_id}",
        json={"nombre": "Nombre Cambiado", "rol": "supervisor"},
        headers=auth_header(admin_token),
    )
    assert r2.status_code == 200
    assert r2.get_json()["nombre"] == "Nombre Cambiado"
    assert r2.get_json()["rol"] == "supervisor"


def test_delete_user_marks_inactive(client, admin_token, auth_header):
    r = client.post(
        "/api/v1/auth/register",
        json={
            "email": "tobedisabled@test.example",
            "password": "secret123",
            "nombre": "ByeBye",
            "rol": "cajero",
        },
        headers=auth_header(admin_token),
    )
    user_id = r.get_json()["id"]

    r2 = client.delete(
        f"/api/v1/auth/users/{user_id}", headers=auth_header(admin_token)
    )
    assert r2.status_code == 204

    rl = client.get("/api/v1/auth/users", headers=auth_header(admin_token))
    target = next(
        u for u in rl.get_json() if u["email"] == "tobedisabled@test.example"
    )
    assert target["activo"] is False
