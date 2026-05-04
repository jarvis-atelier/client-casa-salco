"""Tests del módulo Stock Inteligente — opción C.

Cubre:
- estado_reposicion según min/max/reorden/cantidad
- detector stock_bajo_minimo
- detector sobrestock
- detector rotacion_rapida_faltante (con datos sintéticos de ventas)
- velocidad_venta con datos sintéticos
- sugerir_reposicion devuelve agrupado por proveedor
- POST /reposicion/orden-compra crea factura tipo C borrador
- calcular_stock_optimo con casos borde
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.extensions import db as _db
from app.models.alerta import Alerta, TipoAlertaEnum
from app.models.articulo import Articulo, UnidadMedidaEnum
from app.models.factura import (
    EstadoComprobanteEnum,
    Factura,
    TipoComprobanteEnum,
)
from app.models.factura_item import FacturaItem
from app.models.proveedor import Proveedor
from app.models.stock import StockSucursal
from app.models.sucursal import Sucursal
from app.models.user import RolEnum, User
from app.services.alerts.runner import run_all_detectors
from app.services.analytics.sugerencias_reposicion import (
    calcular_stock_optimo,
    sugerir_reposicion,
)
from app.services.analytics.velocidad_venta import calcular_velocidad_venta
from app.services.auth_service import hash_password


# --- Fixtures locales ---------------------------------------------------------


@pytest.fixture
def sucursal(db):
    s = Sucursal(codigo="SUR1", nombre="Sucursal 1", activa=True)
    db.session.add(s)
    db.session.commit()
    return s


@pytest.fixture
def proveedor(db):
    p = Proveedor(
        codigo="PROVA",
        razon_social="Proveedor A SA",
        activo=True,
        lead_time_dias_default=5,
    )
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture
def articulo(db, proveedor):
    a = Articulo(
        codigo="ART01",
        descripcion="Articulo Stock 01",
        unidad_medida=UnidadMedidaEnum.unidad,
        costo=Decimal("100"),
        pvp_base=Decimal("180"),
        iva_porc=Decimal("21"),
        activo=True,
        controla_stock=True,
        proveedor_principal_id=proveedor.id,
    )
    db.session.add(a)
    db.session.commit()
    return a


@pytest.fixture
def cajero(db, sucursal):
    u = User(
        email="cajero-stk@test.example",
        password_hash=hash_password("cajero123"),
        nombre="Cajero stk",
        rol=RolEnum.cajero,
        sucursal_id=sucursal.id,
        activo=True,
    )
    db.session.add(u)
    db.session.commit()
    return u


def _crear_stock(
    db,
    articulo,
    sucursal,
    *,
    cantidad: Decimal,
    minimo: Decimal | None = None,
    maximo: Decimal | None = None,
    reorden: Decimal | None = None,
    lead_time: int | None = None,
) -> StockSucursal:
    s = StockSucursal(
        articulo_id=articulo.id,
        sucursal_id=sucursal.id,
        cantidad=cantidad,
        stock_minimo=minimo,
        stock_maximo=maximo,
        punto_reorden=reorden,
        lead_time_dias=lead_time,
    )
    db.session.add(s)
    db.session.commit()
    return s


def _registrar_venta(
    db, sucursal, cajero, articulo, cantidad: Decimal, fecha: datetime, numero: int
) -> Factura:
    f = Factura(
        sucursal_id=sucursal.id,
        punto_venta=1,
        tipo=TipoComprobanteEnum.ticket,
        numero=numero,
        fecha=fecha,
        cajero_id=cajero.id,
        estado=EstadoComprobanteEnum.emitida,
        subtotal=Decimal("100") * cantidad,
        total_iva=Decimal("21") * cantidad,
        total=Decimal("121") * cantidad,
    )
    db.session.add(f)
    db.session.flush()
    db.session.add(
        FacturaItem(
            factura_id=f.id,
            articulo_id=articulo.id,
            codigo=articulo.codigo,
            descripcion=articulo.descripcion,
            cantidad=cantidad,
            precio_unitario=Decimal("100"),
            descuento_porc=Decimal("0"),
            iva_porc=Decimal("21"),
            iva_monto=Decimal("21") * cantidad,
            subtotal=Decimal("100") * cantidad,
            total=Decimal("121") * cantidad,
            orden=0,
        )
    )
    db.session.commit()
    return f


# --- Tests: estado_reposicion --------------------------------------------------


def test_estado_reorden(db, articulo, sucursal):
    s = _crear_stock(
        db, articulo, sucursal,
        cantidad=Decimal("15"), minimo=Decimal("10"),
        maximo=Decimal("100"), reorden=Decimal("20"),
    )
    assert s.estado_reposicion == "reorden"
    assert s.efectivo_minimo == Decimal("10")
    assert s.efectivo_reorden == Decimal("20")
    assert s.efectivo_maximo == Decimal("100")


def test_estado_critico(db, articulo, sucursal):
    s = _crear_stock(
        db, articulo, sucursal,
        cantidad=Decimal("8"), minimo=Decimal("10"),
        maximo=Decimal("100"), reorden=Decimal("20"),
    )
    assert s.estado_reposicion == "critico"


def test_estado_agotado(db, articulo, sucursal):
    s = _crear_stock(
        db, articulo, sucursal,
        cantidad=Decimal("0"), minimo=Decimal("10"),
        maximo=Decimal("100"),
    )
    assert s.estado_reposicion == "agotado"


def test_estado_sobrestock(db, articulo, sucursal):
    s = _crear_stock(
        db, articulo, sucursal,
        cantidad=Decimal("150"), minimo=Decimal("10"),
        maximo=Decimal("100"),
    )
    assert s.estado_reposicion == "sobrestock"


def test_estado_ok(db, articulo, sucursal):
    s = _crear_stock(
        db, articulo, sucursal,
        cantidad=Decimal("50"), minimo=Decimal("10"),
        maximo=Decimal("100"), reorden=Decimal("20"),
    )
    assert s.estado_reposicion == "ok"


def test_efectivos_default_articulo(db, articulo, sucursal):
    """Si la sucursal no tiene override, hereda del articulo."""
    articulo.stock_minimo_default = Decimal("5")
    articulo.punto_reorden_default = Decimal("12")
    db.session.commit()

    s = _crear_stock(db, articulo, sucursal, cantidad=Decimal("4"))
    assert s.stock_minimo is None
    assert s.efectivo_minimo == Decimal("5")
    assert s.efectivo_reorden == Decimal("12")
    assert s.estado_reposicion == "critico"


# --- Tests: detectores --------------------------------------------------------


def test_detector_stock_bajo_minimo(db, articulo, sucursal):
    _crear_stock(
        db, articulo, sucursal,
        cantidad=Decimal("3"), minimo=Decimal("10"), maximo=Decimal("80"),
    )
    run_all_detectors(_db.session, ventana_dias=30)
    alerts = (
        _db.session.execute(
            _db.select(Alerta).where(
                Alerta.tipo == TipoAlertaEnum.stock_bajo_minimo
            )
        )
        .scalars()
        .all()
    )
    assert len(alerts) == 1
    assert alerts[0].sucursal_id == sucursal.id
    assert "ART01" in alerts[0].titulo


def test_detector_sobrestock(db, articulo, sucursal):
    _crear_stock(
        db, articulo, sucursal,
        cantidad=Decimal("200"), minimo=Decimal("10"), maximo=Decimal("100"),
    )
    run_all_detectors(_db.session, ventana_dias=30)
    alerts = (
        _db.session.execute(
            _db.select(Alerta).where(
                Alerta.tipo == TipoAlertaEnum.sobrestock
            )
        )
        .scalars()
        .all()
    )
    assert len(alerts) == 1
    assert "200" in alerts[0].titulo


def test_detector_sobrestock_perecedero_severidad_alta(db, articulo, sucursal):
    articulo.controla_vencimiento = True
    db.session.commit()
    _crear_stock(
        db, articulo, sucursal,
        cantidad=Decimal("200"), maximo=Decimal("100"),
    )
    run_all_detectors(_db.session, ventana_dias=30)
    alerts = (
        _db.session.execute(
            _db.select(Alerta).where(
                Alerta.tipo == TipoAlertaEnum.sobrestock
            )
        )
        .scalars()
        .all()
    )
    assert len(alerts) == 1
    assert alerts[0].severidad.value == "alta"
    assert "perecedero" in alerts[0].titulo


def test_detector_rotacion_rapida_faltante(db, articulo, sucursal, cajero):
    """Articulo en 0 + ventas previas → alerta rotacion_rapida_faltante."""
    _crear_stock(db, articulo, sucursal, cantidad=Decimal("0"))
    # Generar 30 ventas, una por día, 2 unidades cada una → 2/dia
    base = datetime.now(timezone.utc)
    for i in range(30):
        _registrar_venta(
            db, sucursal, cajero, articulo,
            cantidad=Decimal("2"),
            fecha=base - timedelta(days=i, hours=1),
            numero=1000 + i,
        )

    run_all_detectors(_db.session, ventana_dias=30)
    alerts = (
        _db.session.execute(
            _db.select(Alerta).where(
                Alerta.tipo == TipoAlertaEnum.rotacion_rapida_faltante
            )
        )
        .scalars()
        .all()
    )
    assert len(alerts) >= 1


# --- Tests: velocidad de venta ------------------------------------------------


def test_velocidad_venta_calcula_promedio(db, articulo, sucursal, cajero):
    base = datetime.now(timezone.utc)
    for i in range(5):
        _registrar_venta(
            db, sucursal, cajero, articulo,
            cantidad=Decimal("4"),
            fecha=base - timedelta(days=i, hours=2),
            numero=2000 + i,
        )
    v = calcular_velocidad_venta(_db.session, articulo.id, sucursal.id, dias=30)
    # 5 días con venta, 4u por día → 20u en 30 días
    assert v["cantidad_total_vendida"] == Decimal("20.0000")
    # 20/30 ≈ 0.6667
    assert Decimal("0.66") <= v["velocidad_promedio_diaria"] <= Decimal("0.67")
    assert v["dias_con_venta"] == 5
    assert v["velocidad_dias_activos"] == Decimal("4.0000")


def test_velocidad_sin_ventas(db, articulo, sucursal):
    v = calcular_velocidad_venta(_db.session, articulo.id, sucursal.id, dias=30)
    assert v["cantidad_total_vendida"] == Decimal("0")
    assert v["velocidad_promedio_diaria"] == Decimal("0")
    assert v["dias_con_venta"] == 0


# --- Tests: stock óptimo (cálculo puro) ---------------------------------------


def test_stock_optimo_calculado():
    # 10/dia × 5 dias × 1.5 = 75
    assert calcular_stock_optimo(Decimal("10"), 5, 1.5) == Decimal("75")
    # velocidad 0 → 0
    assert calcular_stock_optimo(Decimal("0"), 5, 1.5) == Decimal("0")
    # lead time 0 → 0
    assert calcular_stock_optimo(Decimal("10"), 0, 1.5) == Decimal("0")
    # lead time None → 0
    assert calcular_stock_optimo(Decimal("10"), None, 1.5) == Decimal("0")


# --- Tests: sugerir_reposicion ------------------------------------------------


def test_sugerir_reposicion_agrupado_por_proveedor(db, articulo, sucursal, proveedor):
    _crear_stock(
        db, articulo, sucursal,
        cantidad=Decimal("5"), minimo=Decimal("10"),
        maximo=Decimal("100"), reorden=Decimal("20"),
    )
    result = sugerir_reposicion(_db.session, sucursal_id=sucursal.id)
    assert result["totales"]["articulos_a_reponer"] == 1
    assert result["totales"]["sucursales"] == 1
    assert len(result["por_proveedor"]) == 1
    grupo = result["por_proveedor"][0]
    assert grupo["proveedor"]["codigo"] == "PROVA"
    assert len(grupo["items"]) == 1
    item = grupo["items"][0]
    assert item["urgencia"] == "critica"
    assert int(Decimal(item["cantidad_a_pedir"])) > 0


def test_sugerir_reposicion_excluye_ok(db, articulo, sucursal):
    _crear_stock(
        db, articulo, sucursal,
        cantidad=Decimal("50"), minimo=Decimal("10"),
        maximo=Decimal("100"), reorden=Decimal("20"),
    )
    result = sugerir_reposicion(_db.session, sucursal_id=sucursal.id)
    assert result["totales"]["articulos_a_reponer"] == 0
    assert result["por_proveedor"] == []


# --- Tests: endpoint POST /reposicion/orden-compra ----------------------------


def test_post_orden_compra_crea_factura_c_borrador(
    client, admin_token, auth_header, articulo, sucursal, proveedor
):
    payload = {
        "proveedor_id": proveedor.id,
        "sucursal_id": sucursal.id,
        "items": [
            {"articulo_id": articulo.id, "cantidad": "20", "costo_unitario": "100"}
        ],
    }
    r = client.post(
        "/api/v1/reposicion/orden-compra",
        headers=auth_header(admin_token),
        json=payload,
    )
    assert r.status_code == 201, r.get_json()
    data = r.get_json()
    assert data["tipo"] == "factura_c"
    assert data["estado"] == "borrador"

    # Verificar que se creó la factura en DB
    factura = _db.session.get(Factura, data["id"])
    assert factura is not None
    assert factura.estado == EstadoComprobanteEnum.borrador
    assert factura.tipo == TipoComprobanteEnum.factura_c
    assert factura.legacy_meta is not None
    assert factura.legacy_meta["kind"] == "orden_compra_reposicion"
    items = (
        _db.session.execute(
            _db.select(FacturaItem).where(FacturaItem.factura_id == factura.id)
        )
        .scalars()
        .all()
    )
    assert len(items) == 1
    assert items[0].articulo_id == articulo.id
    assert items[0].cantidad == Decimal("20")


# --- Tests: GET /reposicion ---------------------------------------------------


def test_get_reposicion_endpoint(
    client, admin_token, auth_header, db, articulo, sucursal, proveedor
):
    _crear_stock(
        db, articulo, sucursal,
        cantidad=Decimal("3"), minimo=Decimal("10"),
        maximo=Decimal("100"), reorden=Decimal("20"),
    )
    r = client.get(
        f"/api/v1/reposicion?sucursal_id={sucursal.id}",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["totales"]["articulos_a_reponer"] == 1
    assert len(body["por_proveedor"]) == 1


def test_get_reposicion_cajero_forbidden(client, cajero_token, auth_header):
    r = client.get("/api/v1/reposicion", headers=auth_header(cajero_token))
    assert r.status_code == 403


# --- Tests: stock GET con campos efectivos ------------------------------------


def test_get_stock_devuelve_campos_efectivos(
    client, admin_token, auth_header, db, articulo, sucursal
):
    _crear_stock(
        db, articulo, sucursal,
        cantidad=Decimal("3"), minimo=Decimal("10"), maximo=Decimal("100"),
    )
    r = client.get(
        f"/api/v1/stock?sucursal_id={sucursal.id}",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    items = r.get_json()
    assert len(items) == 1
    item = items[0]
    assert item["estado_reposicion"] == "critico"
    assert Decimal(item["efectivo_minimo"]) == Decimal("10")
    assert Decimal(item["efectivo_maximo"]) == Decimal("100")
