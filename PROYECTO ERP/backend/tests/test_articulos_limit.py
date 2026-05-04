"""Tests del alias `limit` en /articulos (compat con per_page)."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.models.articulo import Articulo, UnidadMedidaEnum


@pytest.fixture
def n_articulos(db):
    items = [
        Articulo(
            codigo=f"A{i:03d}",
            descripcion=f"Articulo {i}",
            unidad_medida=UnidadMedidaEnum.unidad,
            costo=Decimal("100"),
            pvp_base=Decimal("150"),
            iva_porc=Decimal("21"),
            activo=True,
        )
        for i in range(0, 12)
    ]
    db.session.add_all(items)
    db.session.commit()
    return items


def test_articulos_limit_alias_works(client, admin_token, auth_header, n_articulos):
    r = client.get("/api/v1/articulos?limit=5", headers=auth_header(admin_token))
    assert r.status_code == 200
    body = r.get_json()
    assert body["per_page"] == 5
    assert len(body["items"]) == 5


def test_articulos_per_page_explicit_takes_precedence(
    client, admin_token, auth_header, n_articulos
):
    # Si se pasa per_page, ignora limit.
    r = client.get(
        "/api/v1/articulos?per_page=3&limit=10", headers=auth_header(admin_token)
    )
    assert r.status_code == 200
    assert r.get_json()["per_page"] == 3
