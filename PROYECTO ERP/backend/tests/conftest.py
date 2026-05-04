"""Fixtures compartidas para pytest."""
from __future__ import annotations

import pytest

from app import create_app
from app.extensions import db as _db
from app.models.user import RolEnum, User
from app.services.auth_service import hash_password


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        }
    )
    with app.app_context():
        _db.create_all()
        yield app
        _db.session.remove()
        _db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    """Expone la sesión db dentro del app context."""
    return _db


@pytest.fixture
def admin_user(db):
    user = User(
        email="admin@test.example",
        password_hash=hash_password("admin123"),
        nombre="Admin Test",
        rol=RolEnum.admin,
        activo=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def supervisor_user(db):
    user = User(
        email="super@test.example",
        password_hash=hash_password("super123"),
        nombre="Super Test",
        rol=RolEnum.supervisor,
        activo=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def cajero_user(db):
    user = User(
        email="cajero@test.example",
        password_hash=hash_password("cajero123"),
        nombre="Cajero Test",
        rol=RolEnum.cajero,
        activo=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


def _login(client, email: str, password: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["access_token"]


@pytest.fixture
def admin_token(client, admin_user):
    return _login(client, "admin@test.example", "admin123")


@pytest.fixture
def supervisor_token(client, supervisor_user):
    return _login(client, "super@test.example", "super123")


@pytest.fixture
def cajero_token(client, cajero_user):
    return _login(client, "cajero@test.example", "cajero123")


@pytest.fixture
def auth_header():
    def _make(token: str) -> dict:
        return {"Authorization": f"Bearer {token}"}

    return _make
