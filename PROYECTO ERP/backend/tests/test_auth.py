"""Tests de autenticación y autorización."""
from __future__ import annotations


def test_login_ok(client, admin_user):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.example", "password": "admin123"},
    )
    assert r.status_code == 200
    body = r.get_json()
    assert "access_token" in body
    assert "refresh_token" in body
    assert body["user"]["email"] == "admin@test.example"
    assert body["user"]["rol"] == "admin"


def test_login_bad_password(client, admin_user):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@test.example", "password": "wrong"},
    )
    assert r.status_code == 401


def test_login_unknown_user(client):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "nope@test.example", "password": "whatever"},
    )
    assert r.status_code == 401


def test_me_ok(client, admin_token, auth_header):
    r = client.get("/api/v1/auth/me", headers=auth_header(admin_token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["email"] == "admin@test.example"
    assert body["rol"] == "admin"


def test_me_requires_jwt(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401


def test_register_requires_admin(client, cajero_token, auth_header):
    r = client.post(
        "/api/v1/auth/register",
        headers=auth_header(cajero_token),
        json={
            "email": "new@test.example",
            "password": "secret1",
            "nombre": "Nuevo",
            "rol": "cajero",
        },
    )
    assert r.status_code == 403


def test_register_admin_ok(client, admin_token, auth_header):
    r = client.post(
        "/api/v1/auth/register",
        headers=auth_header(admin_token),
        json={
            "email": "new@test.example",
            "password": "secret1",
            "nombre": "Nuevo",
            "rol": "cajero",
        },
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["email"] == "new@test.example"
    assert body["rol"] == "cajero"


def test_register_duplicate_email(client, admin_token, auth_header, admin_user):
    r = client.post(
        "/api/v1/auth/register",
        headers=auth_header(admin_token),
        json={
            "email": "admin@test.example",
            "password": "secret1",
            "nombre": "Dup",
            "rol": "cajero",
        },
    )
    assert r.status_code == 409
