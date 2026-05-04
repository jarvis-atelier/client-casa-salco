"""Tests del módulo OCR — upload con mock provider, confirmar (compra),
descartar, RBAC, listado.
"""
from __future__ import annotations

import io
from decimal import Decimal

import pytest

from app.extensions import db as _db
from app.models.articulo import Articulo, UnidadMedidaEnum
from app.models.comprobante_ocr import ComprobanteOcr, EstadoOcrEnum
from app.models.factura import EstadoComprobanteEnum, Factura, TipoComprobanteEnum
from app.models.proveedor import Proveedor
from app.models.stock import StockSucursal
from app.models.sucursal import Sucursal
from app.models.user import RolEnum, User
from app.services.auth_service import hash_password


# -------- Fixtures --------------------------------------------------------------


@pytest.fixture
def sucursal(db):
    s = Sucursal(codigo="OCR", nombre="Sucursal OCR", activa=True)
    db.session.add(s)
    db.session.commit()
    return s


@pytest.fixture
def proveedor_existente(db):
    p = Proveedor(
        codigo="DIST01",
        razon_social="Distribuidora Mock SA",
        cuit="30-12345678-9",
        activo=True,
    )
    db.session.add(p)
    db.session.commit()
    return p


@pytest.fixture
def articulo_existente(db):
    a = Articulo(
        codigo="ART-OCR-1",
        descripcion="Coca Cola 2.25L",
        unidad_medida=UnidadMedidaEnum.unidad,
        costo=Decimal("1500"),
        pvp_base=Decimal("2200"),
        iva_porc=Decimal("21"),
        activo=True,
        controla_stock=True,
    )
    db.session.add(a)
    db.session.commit()
    return a


@pytest.fixture
def cajero_otra_sucursal(db, sucursal):
    other = Sucursal(codigo="OTRA", nombre="Otra Suc", activa=True)
    db.session.add(other)
    db.session.flush()
    user = User(
        email="cajero-otra@test.example",
        password_hash=hash_password("cajero123"),
        nombre="Cajero Otra",
        rol=RolEnum.cajero,
        sucursal_id=other.id,
        activo=True,
    )
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def cajero_otra_token(client, cajero_otra_sucursal):
    r = client.post(
        "/api/v1/auth/login",
        json={"email": "cajero-otra@test.example", "password": "cajero123"},
    )
    assert r.status_code == 200, r.get_json()
    return r.get_json()["access_token"]


def _fake_image(tag: bytes = b"OCR-TEST-PAYLOAD-1") -> io.BytesIO:
    """Genera bytes deterministas. El mock OCR los interpreta vía hash."""
    buf = io.BytesIO(tag * 100)  # asegura suficiente tamaño
    buf.name = "comprobante.jpg"
    return buf


# -------- Tests -----------------------------------------------------------------


def test_upload_mock_devuelve_extraido_con_items(
    client, admin_token, auth_header, sucursal
):
    img = _fake_image()
    r = client.post(
        "/api/v1/ocr/comprobante",
        headers=auth_header(admin_token),
        data={"file": (img, "comprobante.jpg"), "sucursal_id": str(sucursal.id)},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201, r.get_json()
    body = r.get_json()
    assert body["estado"] == "extraido"
    assert body["tipo_detectado"] == "factura"
    assert body["modelo_ia_usado"] == "mock"
    assert len(body["items_extraidos"]) >= 3
    # Cada ítem debe tener los campos clave
    for it in body["items_extraidos"]:
        assert "descripcion" in it
        assert "cantidad" in it
        assert "precio_unitario" in it


def test_upload_matchea_proveedor_por_razon_social(
    client, admin_token, auth_header, sucursal, proveedor_existente
):
    """El mock devuelve 'Distribuidora Mock SA' que está cargada como proveedor."""
    img = _fake_image()
    r = client.post(
        "/api/v1/ocr/comprobante",
        headers=auth_header(admin_token),
        data={"file": (img, "comprobante.jpg"), "sucursal_id": str(sucursal.id)},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201
    body = r.get_json()
    assert body["proveedor_id_match"] == proveedor_existente.id
    assert body["proveedor_match"] is not None
    assert body["proveedor_match"]["razon_social"] == "Distribuidora Mock SA"


def test_confirmar_crea_factura_compra_y_actualiza_stock(
    client, admin_token, auth_header, sucursal, proveedor_existente, articulo_existente
):
    img = _fake_image()
    r = client.post(
        "/api/v1/ocr/comprobante",
        headers=auth_header(admin_token),
        data={"file": (img, "comprobante.jpg"), "sucursal_id": str(sucursal.id)},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201
    comprobante = r.get_json()
    assert comprobante["estado"] == "extraido"

    # Stock inicial
    pre = _db.session.execute(
        _db.select(StockSucursal).where(
            StockSucursal.articulo_id == articulo_existente.id,
            StockSucursal.sucursal_id == sucursal.id,
        )
    ).scalar_one_or_none()
    cantidad_pre = pre.cantidad if pre else Decimal("0")

    # Construyo items: 1 que matchea con un artículo existente, 1 que crea uno nuevo.
    payload = {
        "sucursal_id": sucursal.id,
        "proveedor_id": proveedor_existente.id,
        "items": [
            {
                "descripcion": "Coca Cola 2.25L",
                "cantidad": "10",
                "unidad": "unidad",
                "precio_unitario": "1850.00",
                "iva_porc": "21",
                "articulo_id": articulo_existente.id,
                "crear_articulo_si_falta": False,
            },
            {
                "descripcion": "Producto nuevo desde OCR",
                "cantidad": "5",
                "unidad": "unidad",
                "precio_unitario": "999.99",
                "iva_porc": "21",
                "crear_articulo_si_falta": True,
            },
        ],
    }

    r2 = client.post(
        f"/api/v1/ocr/comprobantes/{comprobante['id']}/confirmar",
        headers=auth_header(admin_token),
        json=payload,
    )
    assert r2.status_code == 200, r2.get_json()
    out = r2.get_json()
    assert out["estado"] == "confirmado"
    assert out["factura_creada_id"] is not None

    # Factura compra creada con tipo factura_c y items.
    fid = out["factura_creada_id"]
    factura = _db.session.get(Factura, fid)
    assert factura is not None
    assert factura.tipo == TipoComprobanteEnum.factura_c
    assert factura.estado == EstadoComprobanteEnum.emitida
    assert factura.sucursal_id == sucursal.id
    assert len(factura.items) == 2
    assert factura.legacy_meta["origen"] == "ocr"
    assert factura.legacy_meta["ocr_id"] == comprobante["id"]

    # Stock subió en el artículo existente.
    post = _db.session.execute(
        _db.select(StockSucursal).where(
            StockSucursal.articulo_id == articulo_existente.id,
            StockSucursal.sucursal_id == sucursal.id,
        )
    ).scalar_one()
    assert post.cantidad == cantidad_pre + Decimal("10")

    # El artículo nuevo se creó.
    art_nuevo = _db.session.execute(
        _db.select(Articulo).where(Articulo.descripcion == "Producto nuevo desde OCR")
    ).scalar_one()
    assert art_nuevo.activo is True
    stock_nuevo = _db.session.execute(
        _db.select(StockSucursal).where(
            StockSucursal.articulo_id == art_nuevo.id,
            StockSucursal.sucursal_id == sucursal.id,
        )
    ).scalar_one()
    assert stock_nuevo.cantidad == Decimal("5")


def test_descartar_marca_estado_descartado(
    client, admin_token, auth_header, sucursal
):
    img = _fake_image()
    r = client.post(
        "/api/v1/ocr/comprobante",
        headers=auth_header(admin_token),
        data={"file": (img, "comprobante.jpg"), "sucursal_id": str(sucursal.id)},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201
    cid = r.get_json()["id"]

    r2 = client.post(
        f"/api/v1/ocr/comprobantes/{cid}/descartar",
        headers=auth_header(admin_token),
    )
    assert r2.status_code == 200
    assert r2.get_json()["estado"] == "descartado"

    # Re-confirmar debe fallar.
    r3 = client.post(
        f"/api/v1/ocr/comprobantes/{cid}/descartar",
        headers=auth_header(admin_token),
    )
    # Descartar dos veces no es error (idempotente: ya estaba descartado, lo dejamos así).
    # Pero confirmar SÍ debe fallar.
    r4 = client.post(
        f"/api/v1/ocr/comprobantes/{cid}/confirmar",
        headers=auth_header(admin_token),
        json={
            "sucursal_id": sucursal.id,
            "items": [
                {
                    "descripcion": "X",
                    "cantidad": "1",
                    "unidad": "unidad",
                    "precio_unitario": "100",
                    "iva_porc": "21",
                }
            ],
        },
    )
    assert r4.status_code == 422


def test_cajero_no_puede_confirmar(
    client, cajero_otra_token, auth_header, sucursal
):
    """Solo admin/supervisor pueden confirmar (crea factura compra)."""
    img = _fake_image()
    # Cajero puede subir
    r = client.post(
        "/api/v1/ocr/comprobante",
        headers=auth_header(cajero_otra_token),
        data={"file": (img, "comprobante.jpg")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 201
    cid = r.get_json()["id"]

    # Pero NO confirmar
    r2 = client.post(
        f"/api/v1/ocr/comprobantes/{cid}/confirmar",
        headers=auth_header(cajero_otra_token),
        json={
            "sucursal_id": sucursal.id,
            "items": [
                {
                    "descripcion": "X",
                    "cantidad": "1",
                    "unidad": "unidad",
                    "precio_unitario": "100",
                    "iva_porc": "21",
                }
            ],
        },
    )
    assert r2.status_code == 403


def test_listar_comprobantes(client, admin_token, auth_header, sucursal):
    for i in range(3):
        img = _fake_image(tag=f"X{i}".encode())
        r = client.post(
            "/api/v1/ocr/comprobante",
            headers=auth_header(admin_token),
            data={"file": (img, f"c{i}.jpg")},
            content_type="multipart/form-data",
        )
        assert r.status_code == 201

    r2 = client.get(
        "/api/v1/ocr/comprobantes?estado=extraido",
        headers=auth_header(admin_token),
    )
    assert r2.status_code == 200
    body = r2.get_json()
    assert body["total"] >= 3
    assert all(it["estado"] == "extraido" for it in body["items"])


def test_mime_invalido_rechazado(client, admin_token, auth_header):
    bad = io.BytesIO(b"not really an image")
    bad.name = "comprobante.txt"
    r = client.post(
        "/api/v1/ocr/comprobante",
        headers=auth_header(admin_token),
        data={"file": (bad, "comprobante.txt", "text/plain")},
        content_type="multipart/form-data",
    )
    assert r.status_code == 422
    assert "mime" in r.get_json()["error"].lower() or "no soportado" in r.get_json()["error"].lower()
