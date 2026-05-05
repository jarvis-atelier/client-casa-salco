"""Fixtures de pytest para tests del ETL.

Asegura que el paquete `app` (backend) es importable y provee una DB
SQLite en memoria con todas las tablas creadas.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Hace visible el paquete `app` del backend ANTES de importar mappers.
# `PROJECT_ROOT` (parent of etl/) se agrega tambien para que los xls mappers
# importen como `from etl.xls.mappers.common_xls import ...` (absoluto desde
# la raiz del proyecto). Los DBF mappers usan imports relativos asi que les
# alcanza con `ETL_ROOT` en sys.path.
ETL_ROOT = Path(__file__).resolve().parent.parent
PROJECT_ROOT = ETL_ROOT.parent
BACKEND_ROOT = PROJECT_ROOT / "backend"
for p in (BACKEND_ROOT, ETL_ROOT, PROJECT_ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pytest  # noqa: E402

from app import create_app  # noqa: E402
from app.extensions import db as _db  # noqa: E402


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
def session(app):
    return _db.session
