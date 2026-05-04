"""Tests del módulo Calendario de pagos — compromisos, pagos, tarjetas, detector."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.extensions import db as _db
from app.models.alerta import Alerta, TipoAlertaEnum
from app.models.calendario_pago import (
    CompromisoPago,
    EstadoCompromisoEnum,
    PagoCompromiso,
    TarjetaCorporativa,
    TipoCompromisoEnum,
)
from app.models.factura import EstadoComprobanteEnum, Factura, TipoComprobanteEnum
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
    p = Proveedor(codigo="PVP01", razon_social="Proveedor Pagos SA", activo=True)
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture
def admin(db):
    u = User(
        email="admin-cal@test.example",
        password_hash=hash_password("admin123"),
        nombre="Admin Cal",
        rol=RolEnum.admin,
        activo=True,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _crear_compromiso(
    db, admin, proveedor=None, monto: str = "120000", venc_offset_days: int = 30
) -> CompromisoPago:
    c = CompromisoPago(
        tipo=TipoCompromisoEnum.factura_compra,
        descripcion="Test compromiso",
        monto_total=Decimal(monto),
        monto_pagado=Decimal("0"),
        fecha_emision=date.today(),
        fecha_vencimiento=date.today() + timedelta(days=venc_offset_days),
        proveedor_id=proveedor.id if proveedor else None,
        creado_por_user_id=admin.id,
    )
    db.session.add(c)
    db.session.commit()
    return c


def _login(client, email: str, password: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.get_json()
    return r.get_json()["access_token"]


@pytest.fixture
def admin_cal_token(client, admin):
    return _login(client, "admin-cal@test.example", "admin123")


# --- Tests de modelo / servicio ------------------------------------------------


def test_crear_compromiso_modelo(db, admin, proveedor):
    c = _crear_compromiso(db, admin, proveedor, monto="50000")
    assert c.id is not None
    assert c.monto_pendiente == Decimal("50000")
    assert c.estado == EstadoCompromisoEnum.pendiente
    assert c.dias_para_vencer == 30


def test_aplicar_pago_parcial_y_total(db, admin, proveedor):
    from app.schemas.calendario_pago import PagoCompromisoCreate
    from app.services.calendario_pagos import aplicar_pago

    c = _crear_compromiso(db, admin, proveedor, monto="100000")

    pago1 = PagoCompromisoCreate(
        monto=Decimal("40000"),
        fecha_pago=date.today(),
        medio_pago="efectivo",
    )
    aplicar_pago(db.session, c, pago1, user_id=admin.id)
    db.session.commit()
    db.session.refresh(c)
    assert c.estado == EstadoCompromisoEnum.parcial
    assert c.monto_pagado == Decimal("40000")
    assert c.monto_pendiente == Decimal("60000")

    pago2 = PagoCompromisoCreate(
        monto=Decimal("60000"),
        fecha_pago=date.today(),
        medio_pago="transferencia",
        referencia="TRX-9871",
    )
    aplicar_pago(db.session, c, pago2, user_id=admin.id)
    db.session.commit()
    db.session.refresh(c)
    assert c.estado == EstadoCompromisoEnum.pagado
    assert c.monto_pagado == Decimal("100000")
    assert c.fecha_pago_real is not None


def test_aplicar_pago_excede_pendiente(db, admin, proveedor):
    from app.schemas.calendario_pago import PagoCompromisoCreate
    from app.services.calendario_pagos import (
        CompromisoValidationError,
        aplicar_pago,
    )

    c = _crear_compromiso(db, admin, proveedor, monto="10000")

    payload = PagoCompromisoCreate(
        monto=Decimal("99999"),
        fecha_pago=date.today(),
        medio_pago="efectivo",
    )
    with pytest.raises(CompromisoValidationError):
        aplicar_pago(db.session, c, payload, user_id=admin.id)


def test_aplicar_pago_genera_movimiento_caja(db, admin, proveedor, sucursal):
    from app.schemas.calendario_pago import PagoCompromisoCreate
    from app.services.calendario_pagos import aplicar_pago

    c = _crear_compromiso(db, admin, proveedor, monto="80000")
    c.sucursal_id = sucursal.id
    db.session.commit()

    payload = PagoCompromisoCreate(
        monto=Decimal("80000"),
        fecha_pago=date.today(),
        medio_pago="efectivo",
        registrar_movimiento_caja=True,
    )
    pago = aplicar_pago(db.session, c, payload, user_id=admin.id)
    db.session.commit()

    assert pago.movimiento_caja_id is not None
    mov = db.session.get(MovimientoCaja, pago.movimiento_caja_id)
    assert mov is not None
    assert mov.tipo == TipoMovimientoEnum.pago_proveedor
    assert mov.proveedor_id == proveedor.id
    assert mov.monto == Decimal("-80000")


def test_auto_generar_desde_factura_c(db, admin, proveedor, sucursal):
    from app.services.calendario_pagos import auto_generar_compromisos

    f = Factura(
        sucursal_id=sucursal.id,
        punto_venta=1,
        tipo=TipoComprobanteEnum.factura_c,
        numero=1,
        fecha=datetime.now(timezone.utc),
        cajero_id=admin.id,
        estado=EstadoComprobanteEnum.emitida,
        subtotal=Decimal("50000"),
        total_iva=Decimal("0"),
        total=Decimal("50000"),
    )
    db.session.add(f)
    db.session.commit()

    res = auto_generar_compromisos(db.session, user_id=admin.id)
    db.session.commit()
    assert res["desde_facturas"] >= 1

    # Idempotencia: un segundo run no crea duplicados.
    res2 = auto_generar_compromisos(db.session, user_id=admin.id)
    db.session.commit()
    assert res2["desde_facturas"] == 0


def test_auto_generar_desde_tarjeta(db, admin):
    from app.services.calendario_pagos import auto_generar_compromisos

    hoy = date.today()
    # Configuro día_cierre = ayer (siempre <= hoy) para forzar generación
    dia_cierre = max(1, hoy.day - 1) if hoy.day > 1 else 1
    t = TarjetaCorporativa(
        nombre="Visa Test",
        ultimos_4="1234",
        dia_cierre=dia_cierre,
        dia_vencimiento=10,
        activa=True,
    )
    db.session.add(t)
    db.session.commit()

    res = auto_generar_compromisos(db.session, user_id=admin.id)
    db.session.commit()
    # Si hoy es día 1, el cierre clampea a 1 = hoy → puede que generemos o no.
    # Lo importante: el segundo run nunca duplica.
    res2 = auto_generar_compromisos(db.session, user_id=admin.id)
    db.session.commit()
    assert res2["desde_tarjetas"] == 0
    # Y si en res hubo creación, hay al menos 1 compromiso de tarjeta.
    if res["desde_tarjetas"] > 0:
        comps = (
            db.session.execute(
                _db.select(CompromisoPago).where(
                    CompromisoPago.tipo == TipoCompromisoEnum.tarjeta_corporativa
                )
            )
            .scalars()
            .all()
        )
        assert len(comps) >= 1


# --- Detector de vencimiento ---------------------------------------------------


def test_detector_vencimiento_proximo(db, admin, proveedor):
    # 1 vencido (hace 2 días), 1 vence hoy, 1 vence en 5 días
    c1 = CompromisoPago(
        tipo=TipoCompromisoEnum.factura_compra,
        descripcion="Vencido hace 2 dias",
        monto_total=Decimal("10000"),
        fecha_vencimiento=date.today() - timedelta(days=2),
        proveedor_id=proveedor.id,
        creado_por_user_id=admin.id,
    )
    c2 = CompromisoPago(
        tipo=TipoCompromisoEnum.servicio,
        descripcion="Vence hoy",
        monto_total=Decimal("20000"),
        fecha_vencimiento=date.today(),
        creado_por_user_id=admin.id,
    )
    c3 = CompromisoPago(
        tipo=TipoCompromisoEnum.factura_compra,
        descripcion="Vence en 5 dias",
        monto_total=Decimal("30000"),
        fecha_vencimiento=date.today() + timedelta(days=5),
        proveedor_id=proveedor.id,
        creado_por_user_id=admin.id,
    )
    db.session.add_all([c1, c2, c3])
    db.session.commit()

    run_all_detectors(_db.session, ventana_dias=30)
    alerts = (
        _db.session.execute(
            _db.select(Alerta).where(
                Alerta.tipo == TipoAlertaEnum.vencimiento_proximo
            )
        )
        .scalars()
        .all()
    )
    assert len(alerts) == 3
    severidades = {a.severidad.value for a in alerts}
    assert "critica" in severidades  # vencido
    assert "alta" in severidades  # hoy


def test_detector_vencimiento_ignora_pagados(db, admin, proveedor):
    c = CompromisoPago(
        tipo=TipoCompromisoEnum.factura_compra,
        descripcion="Ya pagado",
        monto_total=Decimal("10000"),
        monto_pagado=Decimal("10000"),
        estado=EstadoCompromisoEnum.pagado,
        fecha_vencimiento=date.today() + timedelta(days=2),
        proveedor_id=proveedor.id,
        creado_por_user_id=admin.id,
    )
    db.session.add(c)
    db.session.commit()

    run_all_detectors(_db.session, ventana_dias=30)
    alerts = (
        _db.session.execute(
            _db.select(Alerta).where(
                Alerta.tipo == TipoAlertaEnum.vencimiento_proximo
            )
        )
        .scalars()
        .all()
    )
    assert len(alerts) == 0


# --- Endpoints HTTP ------------------------------------------------------------


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_endpoint_create_compromiso(client, admin_cal_token, proveedor):
    payload = {
        "tipo": "factura_compra",
        "descripcion": "Test desde HTTP",
        "monto_total": "55000",
        "fecha_vencimiento": (date.today() + timedelta(days=15)).isoformat(),
        "proveedor_id": proveedor.id,
    }
    r = client.post(
        "/api/v1/compromisos", json=payload, headers=_auth(admin_cal_token)
    )
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["tipo"] == "factura_compra"
    assert body["estado"] == "pendiente"
    assert body["monto_total"] == "55000.00"


def test_endpoint_list_y_resumen(client, admin_cal_token, db, admin, proveedor):
    _crear_compromiso(db, admin, proveedor, monto="20000", venc_offset_days=2)
    _crear_compromiso(db, admin, proveedor, monto="40000", venc_offset_days=-3)

    r = client.get("/api/v1/compromisos", headers=_auth(admin_cal_token))
    assert r.status_code == 200
    data = r.get_json()
    assert data["total"] >= 2

    r = client.get("/api/v1/compromisos/resumen", headers=_auth(admin_cal_token))
    assert r.status_code == 200
    res = r.get_json()
    assert res["vencidos"] >= 1
    assert res["esta_semana"] >= 1


def test_endpoint_pagar(client, admin_cal_token, db, admin, proveedor):
    c = _crear_compromiso(db, admin, proveedor, monto="30000")

    r = client.post(
        f"/api/v1/compromisos/{c.id}/pagar",
        json={
            "monto": "10000",
            "fecha_pago": date.today().isoformat(),
            "medio_pago": "efectivo",
        },
        headers=_auth(admin_cal_token),
    )
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["compromiso"]["estado"] == "parcial"
    assert body["pago"]["monto"] == "10000.00"


def test_endpoint_calendar(client, admin_cal_token, db, admin, proveedor):
    _crear_compromiso(db, admin, proveedor, monto="11111", venc_offset_days=2)
    hoy = date.today()
    r = client.get(
        f"/api/v1/compromisos/calendar?mes={hoy.year:04d}-{hoy.month:02d}",
        headers=_auth(admin_cal_token),
    )
    assert r.status_code == 200
    data = r.get_json()
    assert "items" in data
    assert isinstance(data["items"], list)


def test_endpoint_rbac_cajero_403(client, cajero_token, auth_header):
    r = client.get("/api/v1/compromisos", headers=auth_header(cajero_token))
    assert r.status_code == 403

    r = client.post(
        "/api/v1/compromisos",
        json={
            "tipo": "factura_compra",
            "descripcion": "blocked",
            "monto_total": "100",
            "fecha_vencimiento": date.today().isoformat(),
        },
        headers=auth_header(cajero_token),
    )
    assert r.status_code == 403


def test_endpoint_tarjetas_crud(client, admin_cal_token):
    payload = {
        "nombre": "AMEX Negocios",
        "ultimos_4": "9876",
        "dia_cierre": 15,
        "dia_vencimiento": 5,
    }
    r = client.post("/api/v1/tarjetas", json=payload, headers=_auth(admin_cal_token))
    assert r.status_code == 201, r.get_json()
    tid = r.get_json()["id"]

    r = client.get("/api/v1/tarjetas", headers=_auth(admin_cal_token))
    assert r.status_code == 200
    items = r.get_json()["items"]
    assert any(t["id"] == tid for t in items)

    r = client.patch(
        f"/api/v1/tarjetas/{tid}",
        json={"limite_total": "500000"},
        headers=_auth(admin_cal_token),
    )
    assert r.status_code == 200
    assert r.get_json()["limite_total"] == "500000.00"

    r = client.delete(f"/api/v1/tarjetas/{tid}", headers=_auth(admin_cal_token))
    assert r.status_code == 200
