"""Tests del flujo POS — emisión, stock, anulación, numeración, RBAC."""
from __future__ import annotations

from decimal import Decimal

import pytest

from app.extensions import db as _db
from app.models.articulo import Articulo, UnidadMedidaEnum
from app.models.cliente import Cliente, CondicionIvaEnum
from app.models.factura import EstadoComprobanteEnum, Factura
from app.models.resumen import MovimientoCaja, TipoMovimientoEnum
from app.models.stock import StockSucursal
from app.models.sucursal import Sucursal
from app.models.user import RolEnum, User
from app.services.auth_service import hash_password


# --- Fixtures locales ----------------------------------------------------------


@pytest.fixture
def sucursal_a(db):
    s = Sucursal(codigo="SA", nombre="Sucursal A", activa=True)
    db.session.add(s)
    db.session.commit()
    return s


@pytest.fixture
def sucursal_b(db):
    s = Sucursal(codigo="SB", nombre="Sucursal B", activa=True)
    db.session.add(s)
    db.session.commit()
    return s


@pytest.fixture
def articulos_stock(db, sucursal_a):
    arts = [
        Articulo(
            codigo="X001",
            descripcion="Arroz 1kg",
            unidad_medida=UnidadMedidaEnum.unidad,
            costo=Decimal("600"),
            pvp_base=Decimal("1000"),
            iva_porc=Decimal("21"),
            activo=True,
            controla_stock=True,
        ),
        Articulo(
            codigo="X002",
            descripcion="Coca 2.25L",
            unidad_medida=UnidadMedidaEnum.unidad,
            costo=Decimal("1100"),
            pvp_base=Decimal("2000"),
            iva_porc=Decimal("21"),
            activo=True,
            controla_stock=True,
        ),
    ]
    db.session.add_all(arts)
    db.session.flush()
    for art in arts:
        db.session.add(
            StockSucursal(
                articulo_id=art.id,
                sucursal_id=sucursal_a.id,
                cantidad=Decimal("50"),
            )
        )
    db.session.commit()
    return arts


@pytest.fixture
def consumidor_final(db):
    c = Cliente(
        codigo="CF",
        razon_social="Consumidor Final",
        condicion_iva=CondicionIvaEnum.consumidor_final,
        activo=True,
    )
    db.session.add(c)
    db.session.commit()
    return c


@pytest.fixture
def cajero_sucursal_a(db, sucursal_a):
    user = User(
        email="cajero-a@test.example",
        password_hash=hash_password("cajero123"),
        nombre="Cajero A",
        rol=RolEnum.cajero,
        sucursal_id=sucursal_a.id,
        activo=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def cajero_a_token(client, cajero_sucursal_a):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "cajero-a@test.example", "password": "cajero123"},
    )
    assert r.status_code == 200
    return r.get_json()["access_token"]


# --- Tests ---------------------------------------------------------------------


def test_emitir_ticket_descuenta_stock_y_crea_movimientos(
    client,
    admin_token,
    auth_header,
    sucursal_a,
    articulos_stock,
    consumidor_final,
):
    art1, art2 = articulos_stock
    payload = {
        "sucursal_id": sucursal_a.id,
        "punto_venta": 1,
        "tipo": "ticket",
        "cliente_id": consumidor_final.id,
        "items": [
            {
                "articulo_id": art1.id,
                "cantidad": "2",
                "precio_unitario": "1000",
                "descuento_porc": "0",
            },
            {
                "articulo_id": art2.id,
                "cantidad": "1",
                "precio_unitario": "2000",
                "descuento_porc": "0",
            },
        ],
        # total = (2*1000 + 2000) * 1.21 = 4000 * 1.21 = 4840
        "pagos": [{"medio": "efectivo", "monto": "4840"}],
    }

    r = client.post(
        "/api/v1/facturas", headers=auth_header(admin_token), json=payload
    )
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["tipo"] == "ticket"
    assert body["numero"] == 1
    assert body["estado"] == "emitida"
    assert Decimal(body["total"]) == Decimal("4840.00")
    assert Decimal(body["subtotal"]) == Decimal("4000.00")
    assert Decimal(body["total_iva"]) == Decimal("840.00")
    assert len(body["items"]) == 2
    assert len(body["pagos"]) == 1

    # Stock bajó
    stock_art1 = _db.session.execute(
        _db.select(StockSucursal).where(
            StockSucursal.articulo_id == art1.id,
            StockSucursal.sucursal_id == sucursal_a.id,
        )
    ).scalar_one()
    assert stock_art1.cantidad == Decimal("48")  # 50 - 2

    stock_art2 = _db.session.execute(
        _db.select(StockSucursal).where(
            StockSucursal.articulo_id == art2.id,
            StockSucursal.sucursal_id == sucursal_a.id,
        )
    ).scalar_one()
    assert stock_art2.cantidad == Decimal("49")  # 50 - 1

    # Movimiento caja creado
    movs = (
        _db.session.execute(
            _db.select(MovimientoCaja).where(MovimientoCaja.factura_id == body["id"])
        )
        .scalars()
        .all()
    )
    assert len(movs) == 1
    assert movs[0].tipo == TipoMovimientoEnum.venta
    assert movs[0].monto == Decimal("4840.00")


def test_pagos_insuficientes_rechazados(
    client, admin_token, auth_header, sucursal_a, articulos_stock
):
    art1, _ = articulos_stock
    r = client.post(
        "/api/v1/facturas",
        headers=auth_header(admin_token),
        json={
            "sucursal_id": sucursal_a.id,
            "tipo": "ticket",
            "items": [
                {
                    "articulo_id": art1.id,
                    "cantidad": "1",
                    "precio_unitario": "1000",
                }
            ],
            # total = 1000 * 1.21 = 1210, pagamos 500 → debe fallar
            "pagos": [{"medio": "efectivo", "monto": "500"}],
        },
    )
    assert r.status_code == 422
    assert "pagos" in r.get_json()["error"].lower()


def test_stock_insuficiente_rechazado(
    client, admin_token, auth_header, sucursal_a, articulos_stock
):
    art1, _ = articulos_stock
    r = client.post(
        "/api/v1/facturas",
        headers=auth_header(admin_token),
        json={
            "sucursal_id": sucursal_a.id,
            "tipo": "ticket",
            "items": [
                {
                    "articulo_id": art1.id,
                    "cantidad": "999",  # hay 50
                    "precio_unitario": "1000",
                }
            ],
            "pagos": [{"medio": "efectivo", "monto": str(Decimal("999") * Decimal("1000") * Decimal("1.21"))}],
        },
    )
    assert r.status_code == 422
    assert "stock" in r.get_json()["error"].lower()


def test_numeracion_secuencial(
    client, admin_token, auth_header, sucursal_a, articulos_stock, consumidor_final
):
    art1, _ = articulos_stock

    def _emitir():
        return client.post(
            "/api/v1/facturas",
            headers=auth_header(admin_token),
            json={
                "sucursal_id": sucursal_a.id,
                "punto_venta": 1,
                "tipo": "ticket",
                "cliente_id": consumidor_final.id,
                "items": [
                    {
                        "articulo_id": art1.id,
                        "cantidad": "1",
                        "precio_unitario": "1000",
                    }
                ],
                "pagos": [{"medio": "efectivo", "monto": "1210"}],
            },
        )

    r1 = _emitir()
    assert r1.status_code == 201, r1.get_json()
    r2 = _emitir()
    assert r2.status_code == 201, r2.get_json()

    n1 = r1.get_json()["numero"]
    n2 = r2.get_json()["numero"]
    assert n2 == n1 + 1


def test_anular_restaura_stock(
    client, admin_token, auth_header, sucursal_a, articulos_stock, consumidor_final
):
    art1, _ = articulos_stock
    r = client.post(
        "/api/v1/facturas",
        headers=auth_header(admin_token),
        json={
            "sucursal_id": sucursal_a.id,
            "tipo": "ticket",
            "cliente_id": consumidor_final.id,
            "items": [
                {"articulo_id": art1.id, "cantidad": "5", "precio_unitario": "1000"}
            ],
            "pagos": [{"medio": "efectivo", "monto": "6050"}],
        },
    )
    assert r.status_code == 201
    factura_id = r.get_json()["id"]

    stock_post_venta = _db.session.execute(
        _db.select(StockSucursal).where(
            StockSucursal.articulo_id == art1.id,
            StockSucursal.sucursal_id == sucursal_a.id,
        )
    ).scalar_one()
    assert stock_post_venta.cantidad == Decimal("45")

    r = client.post(
        f"/api/v1/facturas/{factura_id}/anular",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    assert r.get_json()["estado"] == "anulada"

    stock_post_anula = _db.session.execute(
        _db.select(StockSucursal).where(
            StockSucursal.articulo_id == art1.id,
            StockSucursal.sucursal_id == sucursal_a.id,
        )
    ).scalar_one()
    assert stock_post_anula.cantidad == Decimal("50")

    # Existe movimiento inverso (devolucion, monto negativo)
    movs = (
        _db.session.execute(
            _db.select(MovimientoCaja).where(
                MovimientoCaja.factura_id == factura_id,
                MovimientoCaja.tipo == TipoMovimientoEnum.devolucion,
            )
        )
        .scalars()
        .all()
    )
    assert len(movs) == 1
    assert movs[0].monto < 0


def test_cajero_no_puede_facturar_en_otra_sucursal(
    client,
    cajero_a_token,
    auth_header,
    sucursal_a,
    sucursal_b,
    articulos_stock,
    consumidor_final,
):
    # El cajero A intenta facturar en sucursal B → 403
    art1, _ = articulos_stock
    # Agregamos stock en B para que no falle por stock.
    _db.session.add(
        StockSucursal(
            articulo_id=art1.id,
            sucursal_id=sucursal_b.id,
            cantidad=Decimal("50"),
        )
    )
    _db.session.commit()

    r = client.post(
        "/api/v1/facturas",
        headers=auth_header(cajero_a_token),
        json={
            "sucursal_id": sucursal_b.id,
            "tipo": "ticket",
            "cliente_id": consumidor_final.id,
            "items": [
                {"articulo_id": art1.id, "cantidad": "1", "precio_unitario": "1000"}
            ],
            "pagos": [{"medio": "efectivo", "monto": "1210"}],
        },
    )
    assert r.status_code == 403


def test_cajero_puede_facturar_en_su_sucursal(
    client,
    cajero_a_token,
    auth_header,
    sucursal_a,
    articulos_stock,
    consumidor_final,
):
    art1, _ = articulos_stock
    r = client.post(
        "/api/v1/facturas",
        headers=auth_header(cajero_a_token),
        json={
            "sucursal_id": sucursal_a.id,
            "tipo": "ticket",
            "cliente_id": consumidor_final.id,
            "items": [
                {"articulo_id": art1.id, "cantidad": "1", "precio_unitario": "1000"}
            ],
            "pagos": [{"medio": "efectivo", "monto": "1210"}],
        },
    )
    assert r.status_code == 201


def test_get_stock_refleja_decremento(
    client, admin_token, auth_header, sucursal_a, articulos_stock, consumidor_final
):
    art1, _ = articulos_stock
    # Emitir venta
    r = client.post(
        "/api/v1/facturas",
        headers=auth_header(admin_token),
        json={
            "sucursal_id": sucursal_a.id,
            "tipo": "ticket",
            "cliente_id": consumidor_final.id,
            "items": [
                {"articulo_id": art1.id, "cantidad": "3", "precio_unitario": "1000"}
            ],
            "pagos": [{"medio": "efectivo", "monto": "3630"}],
        },
    )
    assert r.status_code == 201

    r = client.get(
        f"/api/v1/stock?articulo_id={art1.id}",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    rows = r.get_json()
    assert len(rows) == 1
    assert Decimal(rows[0]["cantidad"]) == Decimal("47.0000")  # 50 - 3
