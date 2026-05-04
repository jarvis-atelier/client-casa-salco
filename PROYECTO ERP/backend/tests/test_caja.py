"""Tests de abrir/cerrar/estado caja + filtros nuevos en /movimientos."""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.cliente import Cliente, CondicionIvaEnum
from app.models.pago import MedioPagoEnum
from app.models.resumen import MovimientoCaja, TipoMovimientoEnum
from app.models.sucursal import Sucursal


@pytest.fixture
def sucursal_x(db):
    s = Sucursal(codigo="SX", nombre="Sucursal X", activa=True)
    db.session.add(s)
    db.session.commit()
    return s


@pytest.fixture
def cliente_x(db):
    c = Cliente(
        codigo="C1",
        razon_social="Cliente Uno",
        condicion_iva=CondicionIvaEnum.consumidor_final,
        activo=True,
    )
    db.session.add(c)
    db.session.commit()
    return c


def test_abrir_cerrar_caja_flow(client, admin_token, auth_header, sucursal_x):
    # 1) Estado inicial: cerrada.
    r = client.get(
        f"/api/v1/movimientos/estado-caja?sucursal_id={sucursal_x.id}&caja_numero=1",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["abierta"] is False

    # 2) Abrir caja.
    r = client.post(
        "/api/v1/movimientos/abrir-caja",
        json={
            "sucursal_id": sucursal_x.id,
            "caja_numero": 1,
            "monto_inicial": "1000.00",
        },
        headers=auth_header(admin_token),
    )
    assert r.status_code == 201, r.get_json()
    assert r.get_json()["caja_abierta"] is True
    assert r.get_json()["movimiento"]["tipo"] == "apertura_caja"

    # 3) Re-abrir → conflicto.
    r2 = client.post(
        "/api/v1/movimientos/abrir-caja",
        json={"sucursal_id": sucursal_x.id, "caja_numero": 1, "monto_inicial": "0"},
        headers=auth_header(admin_token),
    )
    assert r2.status_code == 409

    # 4) Estado: abierta con teórico = 1000.
    r3 = client.get(
        f"/api/v1/movimientos/estado-caja?sucursal_id={sucursal_x.id}&caja_numero=1",
        headers=auth_header(admin_token),
    )
    assert r3.status_code == 200
    body3 = r3.get_json()
    assert body3["abierta"] is True
    assert Decimal(body3["teorico_efectivo"]) == Decimal("1000")

    # 5) Cerrar con conteo distinto al teórico → diferencia.
    r4 = client.post(
        "/api/v1/movimientos/cerrar-caja",
        json={
            "sucursal_id": sucursal_x.id,
            "caja_numero": 1,
            "conteo_efectivo": "950.00",
            "observacion": "faltaron 50",
        },
        headers=auth_header(admin_token),
    )
    assert r4.status_code == 201, r4.get_json()
    body4 = r4.get_json()
    assert Decimal(body4["diferencia"]) == Decimal("-50")
    assert body4["movimiento"]["tipo"] == "cierre_caja"

    # 6) Estado vuelve a cerrada.
    r5 = client.get(
        f"/api/v1/movimientos/estado-caja?sucursal_id={sucursal_x.id}&caja_numero=1",
        headers=auth_header(admin_token),
    )
    assert r5.status_code == 200
    assert r5.get_json()["abierta"] is False


def test_cerrar_caja_sin_apertura(client, admin_token, auth_header, sucursal_x):
    r = client.post(
        "/api/v1/movimientos/cerrar-caja",
        json={
            "sucursal_id": sucursal_x.id,
            "caja_numero": 2,
            "conteo_efectivo": "0",
        },
        headers=auth_header(admin_token),
    )
    assert r.status_code == 409


def test_movimientos_filter_cliente_id(
    client, admin_token, auth_header, sucursal_x, cliente_x, db
):
    now = datetime.now(UTC)
    db.session.add_all(
        [
            MovimientoCaja(
                sucursal_id=sucursal_x.id,
                caja_numero=1,
                fecha_caja=now.date(),
                fecha=now,
                tipo=TipoMovimientoEnum.cobranza,
                medio=MedioPagoEnum.efectivo,
                monto=Decimal("100"),
                cliente_id=cliente_x.id,
                descripcion="Cobranza",
            ),
            MovimientoCaja(
                sucursal_id=sucursal_x.id,
                caja_numero=1,
                fecha_caja=now.date(),
                fecha=now,
                tipo=TipoMovimientoEnum.venta,
                medio=MedioPagoEnum.efectivo,
                monto=Decimal("200"),
                descripcion="Venta sin cliente",
            ),
        ]
    )
    db.session.commit()

    r = client.get(
        f"/api/v1/movimientos?cliente_id={cliente_x.id}",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert len(items) == 1
    assert items[0]["cliente_id"] == cliente_x.id


def test_movimientos_filter_caja_numero(
    client, admin_token, auth_header, sucursal_x, db
):
    now = datetime.now(UTC)
    db.session.add_all(
        [
            MovimientoCaja(
                sucursal_id=sucursal_x.id,
                caja_numero=1,
                fecha_caja=now.date(),
                fecha=now,
                tipo=TipoMovimientoEnum.venta,
                medio=MedioPagoEnum.efectivo,
                monto=Decimal("100"),
                descripcion="Caja 1",
            ),
            MovimientoCaja(
                sucursal_id=sucursal_x.id,
                caja_numero=2,
                fecha_caja=now.date(),
                fecha=now,
                tipo=TipoMovimientoEnum.venta,
                medio=MedioPagoEnum.efectivo,
                monto=Decimal("200"),
                descripcion="Caja 2",
            ),
        ]
    )
    db.session.commit()

    r = client.get(
        f"/api/v1/movimientos?sucursal_id={sucursal_x.id}&caja_numero=2",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert len(items) == 1
    assert items[0]["caja_numero"] == 2
