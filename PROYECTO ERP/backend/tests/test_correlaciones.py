"""Tests del servicio de market basket analysis (Apriori).

Sintetiza facturas con un patrón conocido (la mitad incluyen A+B juntos)
y verifica que la regla A→B (o B→A) emerge con lift > 1.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.models.articulo import Articulo, UnidadMedidaEnum
from app.models.factura import (
    EstadoComprobanteEnum,
    Factura,
    TipoComprobanteEnum,
)
from app.models.factura_item import FacturaItem
from app.models.sucursal import Sucursal
from app.services.analytics.correlaciones import calcular_correlaciones


@pytest.fixture
def sucursal(db):
    s = Sucursal(codigo="S1", nombre="Sucursal Test", activa=True)
    db.session.add(s)
    db.session.commit()
    return s


@pytest.fixture
def articulos_basket(db):
    """5 artículos para armar transacciones."""
    arts = []
    for i, (codigo, desc) in enumerate(
        [
            ("LEC-001", "Leche La Serenísima 1L"),
            ("PAN-002", "Pan Lactal Bimbo 540g"),
            ("CER-003", "Cerveza Quilmes 1L"),
            ("YER-004", "Yerba Playadito 1kg"),
            ("ACE-005", "Aceite Cocinero 1L"),
        ]
    ):
        a = Articulo(
            codigo=codigo,
            descripcion=desc,
            unidad_medida=UnidadMedidaEnum.unidad,
            costo=Decimal("100"),
            pvp_base=Decimal("200"),
            iva_porc=Decimal("21"),
            activo=True,
            controla_stock=True,
        )
        db.session.add(a)
        arts.append(a)
    db.session.commit()
    return arts


def _factura_con_items(
    db,
    *,
    sucursal_id: int,
    cajero_id: int,
    fecha: datetime,
    arts: list[Articulo],
    numero: int,
) -> Factura:
    f = Factura(
        sucursal_id=sucursal_id,
        punto_venta=1,
        tipo=TipoComprobanteEnum.ticket,
        numero=numero,
        fecha=fecha,
        cajero_id=cajero_id,
        estado=EstadoComprobanteEnum.emitida,
        subtotal=Decimal("0"),
        total_iva=Decimal("0"),
        total=Decimal("0"),
    )
    db.session.add(f)
    db.session.flush()
    for orden, art in enumerate(arts):
        db.session.add(
            FacturaItem(
                factura_id=f.id,
                articulo_id=art.id,
                codigo=art.codigo,
                descripcion=art.descripcion,
                cantidad=Decimal("1"),
                precio_unitario=Decimal("200"),
                descuento_porc=Decimal("0"),
                iva_porc=Decimal("21"),
                iva_monto=Decimal("42"),
                subtotal=Decimal("200"),
                total=Decimal("242"),
                orden=orden,
            )
        )
    db.session.commit()
    return f


def test_apriori_detecta_regla_conocida(db, admin_user, sucursal, articulos_basket):
    """Sintetiza 50 facturas: 25 contienen A+B juntos, 25 contienen otros productos.

    La regla A→B debe aparecer con lift > 1 y confianza alta.
    """
    leche, pan, cerveza, yerba, aceite = articulos_basket
    base = (
        datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=20)
    ).replace(hour=12, minute=0, second=0)

    numero = 1
    # 25 facturas con leche+pan (regla esperada).
    for i in range(25):
        _factura_con_items(
            db,
            sucursal_id=sucursal.id,
            cajero_id=admin_user.id,
            fecha=base + timedelta(hours=i),
            arts=[leche, pan, yerba] if i % 2 == 0 else [leche, pan],
            numero=numero,
        )
        numero += 1
    # 25 facturas SIN leche+pan juntos: distintos pares (cerveza+yerba, aceite+cerveza, etc).
    decoys = [
        [cerveza, yerba],
        [aceite, cerveza],
        [aceite, yerba],
        [cerveza, aceite],
        [yerba, aceite],
    ]
    for i in range(25):
        _factura_con_items(
            db,
            sucursal_id=sucursal.id,
            cajero_id=admin_user.id,
            fecha=base + timedelta(hours=30 + i),
            arts=decoys[i % len(decoys)],
            numero=numero,
        )
        numero += 1

    result = calcular_correlaciones(
        db.session,
        soporte_min=0.05,
        confianza_min=0.5,
        lift_min=1.0,
        top_n=20,
    )

    assert result["transacciones_analizadas"] == 50
    assert result["items_unicos"] >= 5
    assert len(result["reglas"]) >= 1

    leche_id = leche.id
    pan_id = pan.id

    # Buscamos la regla leche→pan (o pan→leche) y verificamos métricas.
    matched = [
        r
        for r in result["reglas"]
        if (
            (leche_id in r["antecedentes_ids"] and pan_id in r["consecuentes_ids"])
            or (pan_id in r["antecedentes_ids"] and leche_id in r["consecuentes_ids"])
        )
    ]
    assert matched, f"No se encontró la regla leche↔pan. Reglas: {result['reglas']}"
    top = matched[0]
    assert top["lift"] > 1.0
    assert top["confianza"] >= 0.5
    assert 0 < top["soporte"] <= 1.0
    # Códigos resueltos correctamente
    todos = top["antecedentes_codigos"] + top["consecuentes_codigos"]
    assert "LEC-001" in todos and "PAN-002" in todos


def test_apriori_sin_facturas_devuelve_vacio(db, sucursal):
    result = calcular_correlaciones(db.session, soporte_min=0.01)
    assert result["transacciones_analizadas"] == 0
    assert result["reglas"] == []


def test_endpoint_correlaciones_requiere_admin(
    client, cajero_token, auth_header
):
    r = client.get(
        "/api/v1/reports/correlaciones",
        headers=auth_header(cajero_token),
    )
    assert r.status_code == 403


def test_endpoint_correlaciones_admin_ok(
    client, db, admin_user, admin_token, auth_header, sucursal, articulos_basket
):
    """Con datos suficientes, el endpoint devuelve la regla esperada."""
    leche, pan, cerveza, yerba, aceite = articulos_basket
    base = (
        datetime.now(timezone.utc).replace(microsecond=0) - timedelta(days=10)
    ).replace(hour=10, minute=0, second=0)
    numero = 1
    for i in range(20):
        _factura_con_items(
            db,
            sucursal_id=sucursal.id,
            cajero_id=admin_user.id,
            fecha=base + timedelta(hours=i),
            arts=[leche, pan],
            numero=numero,
        )
        numero += 1
    for i in range(15):
        _factura_con_items(
            db,
            sucursal_id=sucursal.id,
            cajero_id=admin_user.id,
            fecha=base + timedelta(hours=30 + i),
            arts=[cerveza, yerba] if i % 2 == 0 else [aceite, yerba],
            numero=numero,
        )
        numero += 1

    r = client.get(
        "/api/v1/reports/correlaciones?soporte_min=0.05&confianza_min=0.5&lift_min=1.0",
        headers=auth_header(admin_token),
    )
    assert r.status_code == 200, r.get_json()
    body = r.get_json()
    assert body["transacciones_analizadas"] == 35
    assert isinstance(body["reglas"], list)
    assert "params" in body
    # Cache flag presente
    assert "cached" in body
