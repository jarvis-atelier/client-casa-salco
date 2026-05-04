"""Tests del módulo de alertas — detección, idempotencia, RBAC, resumen, patch."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.extensions import db as _db
from app.models.alerta import Alerta, EstadoAlertaEnum, TipoAlertaEnum
from app.models.factura import (
    EstadoComprobanteEnum,
    Factura,
    TipoComprobanteEnum,
)
from app.models.factura_item import FacturaItem
from app.models.proveedor import Proveedor
from app.models.resumen import MovimientoCaja, TipoMovimientoEnum
from app.models.sucursal import Sucursal
from app.models.user import RolEnum, User
from app.services.alerts.runner import run_all_detectors
from app.services.auth_service import hash_password


# --- Fixtures locales ----------------------------------------------------------


@pytest.fixture
def sucursal(db):
    s = Sucursal(codigo="SX", nombre="Sucursal X", activa=True)
    db.session.add(s)
    db.session.commit()
    return s


@pytest.fixture
def proveedor(db):
    p = Proveedor(codigo="PROV01", razon_social="Proveedor Test SA", activo=True)
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture
def cajero(db, sucursal):
    u = User(
        email="cajero-x@test.example",
        password_hash=hash_password("cajero123"),
        nombre="Cajero X",
        rol=RolEnum.cajero,
        sucursal_id=sucursal.id,
        activo=True,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _create_pago_proveedor(
    sucursal, proveedor, monto: Decimal, fecha: datetime
) -> MovimientoCaja:
    m = MovimientoCaja(
        sucursal_id=sucursal.id,
        caja_numero=1,
        fecha_caja=fecha.date(),
        fecha=fecha,
        tipo=TipoMovimientoEnum.pago_proveedor,
        monto=-monto,
        proveedor_id=proveedor.id,
        descripcion=f"Pago proveedor {monto}",
    )
    _db.session.add(m)
    _db.session.commit()
    return m


# --- Tests de detección --------------------------------------------------------


def test_pago_duplicado_detectado(db, sucursal, proveedor):
    now = datetime.now(timezone.utc)
    _create_pago_proveedor(sucursal, proveedor, Decimal("100000"), now)
    _create_pago_proveedor(sucursal, proveedor, Decimal("100000"), now + timedelta(days=2)
    )

    result = run_all_detectors(_db.session, ventana_dias=30)

    assert result["creadas"] >= 1
    alerts = (
        _db.session.execute(
            _db.select(Alerta).where(
                Alerta.tipo == TipoAlertaEnum.pago_duplicado
            )
        )
        .scalars()
        .all()
    )
    assert len(alerts) >= 1
    a = alerts[0]
    assert a.proveedor_id == proveedor.id
    assert "100000" in a.descripcion or "100000.00" in a.descripcion
    assert a.deteccion_hash and len(a.deteccion_hash) == 64


def test_runner_idempotente_no_duplica(db, sucursal, proveedor):
    now = datetime.now(timezone.utc)
    _create_pago_proveedor(sucursal, proveedor, Decimal("50000"), now)
    _create_pago_proveedor(sucursal, proveedor, Decimal("50000"), now + timedelta(days=1)
    )

    r1 = run_all_detectors(_db.session, ventana_dias=30)
    assert r1["creadas"] >= 1
    total1 = _db.session.scalar(_db.select(_db.func.count(Alerta.id)))

    # Segunda corrida: NO crea nada nuevo (mismo hash)
    r2 = run_all_detectors(_db.session, ventana_dias=30)
    assert r2["creadas"] == 0
    total2 = _db.session.scalar(_db.select(_db.func.count(Alerta.id)))
    assert total1 == total2


def test_factura_compra_repetida_detectada(db, sucursal, proveedor):
    now = datetime.now(timezone.utc)
    # Tres pagos con MISMO total al mismo proveedor en menos de 7 días
    _create_pago_proveedor(sucursal, proveedor, Decimal("75000.50"), now)
    _create_pago_proveedor(sucursal, proveedor, Decimal("75000.50"), now + timedelta(days=3)
    )
    _create_pago_proveedor(sucursal, proveedor, Decimal("75000.50"), now + timedelta(days=5)
    )

    run_all_detectors(_db.session, ventana_dias=30)

    repetidas = (
        _db.session.execute(
            _db.select(Alerta).where(
                Alerta.tipo == TipoAlertaEnum.factura_compra_repetida
            )
        )
        .scalars()
        .all()
    )
    assert len(repetidas) >= 1
    assert repetidas[0].severidad.value == "alta"
    assert repetidas[0].proveedor_id == proveedor.id


def test_anulaciones_frecuentes_dia(db, sucursal, cajero):
    now = datetime.now(timezone.utc)
    # 4 anuladas el mismo día (umbral > 3)
    for i in range(4):
        f = Factura(
            sucursal_id=sucursal.id,
            punto_venta=1,
            tipo=TipoComprobanteEnum.ticket,
            numero=i + 1,
            fecha=now - timedelta(hours=i),
            cajero_id=cajero.id,
            estado=EstadoComprobanteEnum.anulada,
            subtotal=Decimal("1000"),
            total_iva=Decimal("210"),
            total=Decimal("1210"),
        )
        db.session.add(f)
    db.session.commit()

    run_all_detectors(_db.session, ventana_dias=30)
    alerts = (
        _db.session.execute(
            _db.select(Alerta).where(
                Alerta.tipo == TipoAlertaEnum.anulaciones_frecuentes
            )
        )
        .scalars()
        .all()
    )
    assert len(alerts) >= 1
    assert alerts[0].user_relacionado_id == cajero.id


def test_items_repetidos_detectado(db, sucursal, cajero):
    """Mismo articulo+cantidad+precio en 2 facturas distintas, mismo cajero, < 30 min."""
    from app.models.articulo import Articulo, UnidadMedidaEnum

    art = Articulo(
        codigo="A001",
        descripcion="Articulo Test",
        unidad_medida=UnidadMedidaEnum.unidad,
        costo=Decimal("50"),
        pvp_base=Decimal("100"),
        iva_porc=Decimal("21"),
        activo=True,
        controla_stock=True,
    )
    db.session.add(art)
    db.session.flush()

    now = datetime.now(timezone.utc)
    f1 = Factura(
        sucursal_id=sucursal.id,
        punto_venta=1,
        tipo=TipoComprobanteEnum.ticket,
        numero=100,
        fecha=now,
        cajero_id=cajero.id,
        estado=EstadoComprobanteEnum.emitida,
        subtotal=Decimal("100"),
        total_iva=Decimal("21"),
        total=Decimal("121"),
    )
    f2 = Factura(
        sucursal_id=sucursal.id,
        punto_venta=1,
        tipo=TipoComprobanteEnum.ticket,
        numero=101,
        fecha=now + timedelta(minutes=5),
        cajero_id=cajero.id,
        estado=EstadoComprobanteEnum.emitida,
        subtotal=Decimal("100"),
        total_iva=Decimal("21"),
        total=Decimal("121"),
    )
    db.session.add_all([f1, f2])
    db.session.flush()
    for f in (f1, f2):
        db.session.add(
            FacturaItem(
                factura_id=f.id,
                articulo_id=art.id,
                codigo=art.codigo,
                descripcion=art.descripcion,
                cantidad=Decimal("1"),
                precio_unitario=Decimal("100"),
                descuento_porc=Decimal("0"),
                iva_porc=Decimal("21"),
                iva_monto=Decimal("21"),
                subtotal=Decimal("100"),
                total=Decimal("121"),
                orden=0,
            )
        )
    db.session.commit()

    run_all_detectors(_db.session, ventana_dias=30)
    alerts = (
        _db.session.execute(
            _db.select(Alerta).where(
                Alerta.tipo == TipoAlertaEnum.items_repetidos_diff_nro
            )
        )
        .scalars()
        .all()
    )
    assert len(alerts) >= 1


def test_ajuste_stock_sospechoso(db, sucursal, cajero):
    now = datetime.now(timezone.utc)
    db.session.add(
        MovimientoCaja(
            sucursal_id=sucursal.id,
            caja_numero=1,
            fecha_caja=now.date(),
            fecha=now,
            tipo=TipoMovimientoEnum.ajuste,
            monto=Decimal("-25000"),
            descripcion="Ajuste manual de stock",
            user_id=cajero.id,
        )
    )
    db.session.commit()

    run_all_detectors(_db.session, ventana_dias=30)
    alerts = (
        _db.session.execute(
            _db.select(Alerta).where(
                Alerta.tipo == TipoAlertaEnum.ajuste_stock_sospechoso
            )
        )
        .scalars()
        .all()
    )
    assert len(alerts) >= 1


# --- Tests de endpoints --------------------------------------------------------


def test_get_alertas_admin_only(client, cajero_token, auth_header):
    r = client.get("/api/v1/alertas", headers=auth_header(cajero_token))
    assert r.status_code == 403


def test_get_alertas_admin_ok(client, admin_token, auth_header, sucursal, proveedor):
    now = datetime.now(timezone.utc)
    _create_pago_proveedor(sucursal, proveedor, Decimal("12345"), now)
    _create_pago_proveedor(sucursal, proveedor, Decimal("12345"), now + timedelta(days=1)
    )

    # Run detección
    r = client.post(
        "/api/v1/alertas/run", headers=auth_header(admin_token)
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["creadas"] >= 1

    r = client.get("/api/v1/alertas", headers=auth_header(admin_token))
    assert r.status_code == 200
    data = r.get_json()
    assert data["total"] >= 1
    assert len(data["items"]) >= 1
    assert "tipo" in data["items"][0]


def test_resumen_endpoint(client, admin_token, auth_header, sucursal, proveedor):
    now = datetime.now(timezone.utc)
    _create_pago_proveedor(sucursal, proveedor, Decimal("8000"), now)
    _create_pago_proveedor(sucursal, proveedor, Decimal("8000"), now + timedelta(days=1)
    )
    run_all_detectors(_db.session, ventana_dias=30)

    r = client.get("/api/v1/alertas/resumen", headers=auth_header(admin_token))
    assert r.status_code == 200
    data = r.get_json()
    assert "nuevas" in data
    assert "criticas" in data
    assert "ultimas_24h" in data
    assert "total_abiertas" in data
    assert data["nuevas"] >= 1
    assert data["criticas"] >= 1


def test_patch_estado(client, admin_token, auth_header, sucursal, proveedor):
    now = datetime.now(timezone.utc)
    _create_pago_proveedor(sucursal, proveedor, Decimal("7000"), now)
    _create_pago_proveedor(sucursal, proveedor, Decimal("7000"), now + timedelta(days=1)
    )
    run_all_detectors(_db.session, ventana_dias=30)
    alerta = _db.session.execute(_db.select(Alerta).limit(1)).scalar_one()

    r = client.patch(
        f"/api/v1/alertas/{alerta.id}",
        headers=auth_header(admin_token),
        json={"estado": "descartada", "nota_resolucion": "falso positivo"},
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["estado"] == "descartada"
    assert body["nota_resolucion"] == "falso positivo"
    assert body["resolved_at"] is not None


def test_get_alerta_detalle(client, admin_token, auth_header, sucursal, proveedor):
    now = datetime.now(timezone.utc)
    _create_pago_proveedor(sucursal, proveedor, Decimal("9999"), now)
    _create_pago_proveedor(sucursal, proveedor, Decimal("9999"), now + timedelta(days=1)
    )
    run_all_detectors(_db.session, ventana_dias=30)
    alerta = _db.session.execute(_db.select(Alerta).limit(1)).scalar_one()

    r = client.get(
        f"/api/v1/alertas/{alerta.id}", headers=auth_header(admin_token)
    )
    assert r.status_code == 200
    data = r.get_json()
    assert "proveedor" in data
    assert data["proveedor"] is not None
    assert data["proveedor"]["id"] == proveedor.id


def test_delete_solo_si_descartada(client, admin_token, auth_header, sucursal, proveedor):
    now = datetime.now(timezone.utc)
    _create_pago_proveedor(sucursal, proveedor, Decimal("5000"), now)
    _create_pago_proveedor(sucursal, proveedor, Decimal("5000"), now + timedelta(days=1)
    )
    run_all_detectors(_db.session, ventana_dias=30)
    alerta = _db.session.execute(_db.select(Alerta).limit(1)).scalar_one()

    # Mientras esté en estado nueva → 422
    r = client.delete(
        f"/api/v1/alertas/{alerta.id}", headers=auth_header(admin_token)
    )
    assert r.status_code == 422

    # Pasarla a descartada
    client.patch(
        f"/api/v1/alertas/{alerta.id}",
        headers=auth_header(admin_token),
        json={"estado": "descartada"},
    )
    # Ahora sí
    r = client.delete(
        f"/api/v1/alertas/{alerta.id}", headers=auth_header(admin_token)
    )
    assert r.status_code == 200


def test_run_endpoint_admin_only(client, cajero_token, auth_header):
    r = client.post("/api/v1/alertas/run", headers=auth_header(cajero_token))
    assert r.status_code == 403


def test_resumen_admin_only(client, supervisor_token, auth_header):
    r = client.get(
        "/api/v1/alertas/resumen", headers=auth_header(supervisor_token)
    )
    assert r.status_code == 403
