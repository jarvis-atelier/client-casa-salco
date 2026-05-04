"""Tests de los endpoints de reports (dashboard agregations)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.extensions import db as _db
from app.models.articulo import Articulo, UnidadMedidaEnum
from app.models.cliente import Cliente, CondicionIvaEnum
from app.models.factura import (
    EstadoComprobanteEnum,
    Factura,
    TipoComprobanteEnum,
)
from app.models.factura_item import FacturaItem
from app.models.pago import FacturaPago, MedioPagoEnum
from app.models.stock import StockSucursal
from app.models.sucursal import Sucursal


# --- Fixtures ----------------------------------------------------------------


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
def articulos_demo(db, sucursal_a, sucursal_b):
    arts = [
        Articulo(
            codigo="P001",
            descripcion="Pan lactal",
            unidad_medida=UnidadMedidaEnum.unidad,
            costo=Decimal("500"),
            pvp_base=Decimal("1000"),
            iva_porc=Decimal("21"),
            activo=True,
            controla_stock=True,
        ),
        Articulo(
            codigo="P002",
            descripcion="Coca cola 2L",
            unidad_medida=UnidadMedidaEnum.unidad,
            costo=Decimal("1500"),
            pvp_base=Decimal("2500"),
            iva_porc=Decimal("21"),
            activo=True,
            controla_stock=True,
        ),
    ]
    db.session.add_all(arts)
    db.session.flush()
    for art in arts:
        for suc in (sucursal_a, sucursal_b):
            db.session.add(
                StockSucursal(
                    articulo_id=art.id,
                    sucursal_id=suc.id,
                    cantidad=Decimal("100"),
                )
            )
    db.session.commit()
    return arts


def _make_factura(
    db,
    *,
    sucursal_id: int,
    cajero_id: int,
    fecha: datetime,
    items: list[tuple[int, str, Decimal, Decimal]],
    pagos: list[tuple[MedioPagoEnum, Decimal]],
    tipo: TipoComprobanteEnum = TipoComprobanteEnum.ticket,
    numero: int = 1,
) -> Factura:
    """Crea una factura de prueba directamente (skip pos_service para flexibilidad temporal)."""
    subtotal = sum((c * p for _, _, c, p in items), Decimal("0"))
    iva_total = sum((c * p * Decimal("0.21") for _, _, c, p in items), Decimal("0"))
    total = subtotal + iva_total
    factura = Factura(
        sucursal_id=sucursal_id,
        punto_venta=1,
        tipo=tipo,
        numero=numero,
        fecha=fecha,
        cajero_id=cajero_id,
        estado=EstadoComprobanteEnum.emitida,
        subtotal=subtotal.quantize(Decimal("0.01")),
        total_iva=iva_total.quantize(Decimal("0.01")),
        total=total.quantize(Decimal("0.01")),
    )
    db.session.add(factura)
    db.session.flush()
    for orden, (art_id, codigo, cantidad, precio) in enumerate(items):
        line_sub = cantidad * precio
        line_iva = line_sub * Decimal("0.21")
        db.session.add(
            FacturaItem(
                factura_id=factura.id,
                articulo_id=art_id,
                codigo=codigo,
                descripcion=f"Articulo {codigo}",
                cantidad=cantidad,
                precio_unitario=precio,
                descuento_porc=Decimal("0"),
                iva_porc=Decimal("21"),
                iva_monto=line_iva.quantize(Decimal("0.0001")),
                subtotal=line_sub.quantize(Decimal("0.0001")),
                total=(line_sub + line_iva).quantize(Decimal("0.0001")),
                orden=orden,
            )
        )
    for orden, (medio, monto) in enumerate(pagos):
        db.session.add(
            FacturaPago(
                factura_id=factura.id,
                medio=medio,
                monto=monto.quantize(Decimal("0.01")),
                orden=orden,
            )
        )
    db.session.commit()
    return factura


@pytest.fixture
def facturas_seed(db, admin_user, sucursal_a, sucursal_b, articulos_demo):
    """Crea 4 facturas distribuidas en 3 días + 2 sucursales + medios de pago variados."""
    art1, art2 = articulos_demo
    # Usamos fechas claramente DENTRO de los últimos 30 días (entre 5 y 8 días atrás)
    # para evitar que problemas de timezone con `date.today()` corten facturas.
    now = datetime.now(timezone.utc).replace(microsecond=0)
    base_today = (now - timedelta(days=5)).replace(hour=11, minute=0, second=0)
    yesterday = base_today - timedelta(days=1)
    two_days_ago = base_today - timedelta(days=2)

    f1 = _make_factura(
        db,
        sucursal_id=sucursal_a.id,
        cajero_id=admin_user.id,
        fecha=base_today,
        items=[(art1.id, "P001", Decimal("3"), Decimal("1000"))],
        pagos=[(MedioPagoEnum.efectivo, Decimal("3630"))],
        numero=1,
    )
    f2 = _make_factura(
        db,
        sucursal_id=sucursal_a.id,
        cajero_id=admin_user.id,
        fecha=base_today.replace(hour=18),
        items=[(art2.id, "P002", Decimal("2"), Decimal("2500"))],
        pagos=[(MedioPagoEnum.tarjeta_credito, Decimal("6050"))],
        numero=2,
    )
    f3 = _make_factura(
        db,
        sucursal_id=sucursal_b.id,
        cajero_id=admin_user.id,
        fecha=yesterday,
        items=[
            (art1.id, "P001", Decimal("1"), Decimal("1000")),
            (art2.id, "P002", Decimal("1"), Decimal("2500")),
        ],
        pagos=[(MedioPagoEnum.qr_mercadopago, Decimal("4235"))],
        numero=1,
    )
    f4 = _make_factura(
        db,
        sucursal_id=sucursal_b.id,
        cajero_id=admin_user.id,
        fecha=two_days_ago,
        items=[(art1.id, "P001", Decimal("5"), Decimal("1000"))],
        pagos=[(MedioPagoEnum.efectivo, Decimal("6050"))],
        numero=2,
    )
    return [f1, f2, f3, f4]


# --- Tests -------------------------------------------------------------------


def test_ventas_resumen_returns_kpis(
    client, admin_token, auth_header, facturas_seed
):
    r = client.get(
        "/api/v1/reports/ventas-resumen",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["total_facturas"] == 4
    # Suma esperada: 3630 + 6050 + 4235 + 6050 = 19965
    assert Decimal(body["total_facturado"]) == Decimal("19965.00")
    assert Decimal(body["total_iva"]) > Decimal("0")
    assert Decimal(body["ticket_promedio"]) > Decimal("0")
    # Breakdown por sucursal: dos códigos
    codigos = {row["codigo"] for row in body["por_sucursal"]}
    assert codigos == {"SA", "SB"}


def test_ventas_resumen_filtra_por_sucursal(
    client, admin_token, auth_header, sucursal_a, facturas_seed
):
    r = client.get(
        f"/api/v1/reports/ventas-resumen?sucursal_id={sucursal_a.id}",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200
    body = r.get_json()
    assert body["total_facturas"] == 2  # f1 y f2
    # 3630 + 6050 = 9680
    assert Decimal(body["total_facturado"]) == Decimal("9680.00")


def test_ventas_por_dia_agrupa_correctamente(
    client, admin_token, auth_header, facturas_seed
):
    r = client.get(
        "/api/v1/reports/ventas-por-dia",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    # Debe haber al menos 3 días distintos
    assert len(body) >= 3
    # Cada item tiene shape esperado
    for item in body:
        assert "fecha" in item
        assert "total" in item
        assert "cantidad" in item
        assert "por_sucursal" in item
    # La suma de totales == 19965
    total = sum(Decimal(it["total"]) for it in body)
    assert total == Decimal("19965.00")


def test_top_productos_ordena_por_cantidad(
    client, admin_token, auth_header, facturas_seed, articulos_demo
):
    r = client.get(
        "/api/v1/reports/top-productos?limit=5",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert len(body) == 2  # Sólo 2 artículos en el seed
    # P001 tiene 3+1+5 = 9 unidades, P002 tiene 2+1 = 3
    top = body[0]
    assert top["codigo"] == "P001"
    assert Decimal(top["cantidad_vendida"]) == Decimal("9.00")


def test_ventas_por_hora_devuelve_celdas(
    client, admin_token, auth_header, facturas_seed
):
    r = client.get(
        "/api/v1/reports/ventas-por-hora",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert isinstance(body, list)
    assert len(body) >= 1
    for row in body:
        assert 0 <= row["dia_semana"] <= 6
        assert 0 <= row["hora"] <= 23
        assert row["cantidad"] >= 1


def test_medios_pago_distribucion(
    client, admin_token, auth_header, facturas_seed
):
    r = client.get(
        "/api/v1/reports/medios-pago",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    medios = {row["medio"] for row in body}
    # Tres medios usados: efectivo, tarjeta_credito, qr_mercadopago
    assert medios == {"efectivo", "tarjeta_credito", "qr_mercadopago"}
    # Suma de porcentajes ~= 100
    total_porc = sum(row["porc"] for row in body)
    assert abs(total_porc - 100) < 1.0
    # Suma de totales == 19965
    total_pagado = sum(Decimal(row["total"]) for row in body)
    assert total_pagado == Decimal("19965.00")


def test_reports_require_auth(client):
    r = client.get("/api/v1/reports/ventas-resumen")
    assert r.status_code == 401
