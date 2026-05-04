"""Tests del servicio AFIP — MockProvider, QR, factory.

NO testea PyAfipWsProvider contra AFIP real — eso requiere cert + network.
Dejamos un test marcado con skip condicional para integracion manual.
"""
from __future__ import annotations

import base64
import json
import os
from datetime import date
from decimal import Decimal

import pytest

from app.services.afip import (
    AfipFacturaInput,
    MockProvider,
    generar_qr_url,
    get_provider,
)
from app.services.afip.tipos import (
    COND_IVA_RECEPTOR_RG_5616,
    TIPO_AFIP_MAP,
    get_cond_iva_receptor,
    get_tipo_afip,
)


# ------------------------------------------------------------------ MockProvider


def _sample_input(**overrides) -> AfipFacturaInput:
    defaults = dict(
        cuit_emisor="20000000001",
        tipo_afip=6,  # Factura B
        punto_venta=1,
        concepto=1,
        tipo_doc_receptor=99,
        nro_doc_receptor="0",
        cond_iva_receptor_id=COND_IVA_RECEPTOR_RG_5616["consumidor_final"],
        fecha_comprobante=date.today(),
        importe_neto=Decimal("100.00"),
        importe_iva=Decimal("21.00"),
        importe_total=Decimal("121.00"),
        items_iva=[{"alic": 5, "base": Decimal("100.00"), "iva": Decimal("21.00")}],
    )
    defaults.update(overrides)
    return AfipFacturaInput(**defaults)


def test_mock_provider_generates_cae():
    provider = MockProvider()
    output = provider.solicitar_cae(_sample_input())

    assert output.cae != ""
    assert len(output.cae) == 14
    assert output.cae.isdigit()
    assert output.resultado == "A"
    assert output.reproceso == "N"
    assert output.numero_comprobante == 1
    assert output.fecha_vencimiento >= date.today()


def test_mock_provider_increments_numero_comprobante():
    provider = MockProvider()
    out1 = provider.solicitar_cae(_sample_input())
    out2 = provider.solicitar_cae(_sample_input())
    out3 = provider.solicitar_cae(_sample_input(punto_venta=2))

    assert out1.numero_comprobante == 1
    assert out2.numero_comprobante == 2
    # Distinto punto_venta mantiene counter separado.
    assert out3.numero_comprobante == 1


def test_mock_provider_ultimo_autorizado_inicia_en_cero():
    provider = MockProvider()
    assert provider.ultimo_autorizado("20000000001", 6, 1) == 0
    provider.solicitar_cae(_sample_input())
    assert provider.ultimo_autorizado("20000000001", 6, 1) == 1


def test_mock_provider_diferentes_caes():
    """Dos solicitudes consecutivas deben dar CAEs distintos (deterministico por timestamp)."""
    provider = MockProvider()
    out1 = provider.solicitar_cae(_sample_input())
    # Pequena demora implicita por el timestamp microsec — suficiente para diferir.
    out2 = provider.solicitar_cae(_sample_input())
    assert out1.cae != out2.cae


# ------------------------------------------------------------------ QR AFIP


def test_generar_qr_url_format():
    url = generar_qr_url(
        cuit="20000000001",
        pto_vta=1,
        tipo_cmp=6,
        nro_cmp=123,
        importe=Decimal("121.00"),
        cae="12345678901234",
        fecha=date(2026, 4, 24),
        tipo_doc_rec=99,
        nro_doc_rec="0",
    )
    assert url.startswith("https://www.afip.gob.ar/fe/qr/?p=")

    # Decodificar y verificar el JSON embedded.
    encoded = url.split("?p=", 1)[1]
    # urlsafe_b64decode requiere padding — la libreria no lo pone porque el JSON
    # es multiplo de 3 la mayoria de las veces pero por las dudas aqui ajustamos.
    pad = "=" * (-len(encoded) % 4)
    decoded = base64.urlsafe_b64decode(encoded + pad).decode("utf-8")
    payload = json.loads(decoded)

    assert payload["ver"] == 1
    assert payload["fecha"] == "2026-04-24"
    assert payload["cuit"] == 20000000001
    assert payload["ptoVta"] == 1
    assert payload["tipoCmp"] == 6
    assert payload["nroCmp"] == 123
    assert payload["importe"] == 121.00
    assert payload["moneda"] == "PES"
    assert payload["ctz"] == 1.0
    assert payload["tipoDocRec"] == 99
    assert payload["nroDocRec"] == 0
    assert payload["tipoCodAut"] == "E"
    assert payload["codAut"] == 12345678901234


def test_generar_qr_url_acepta_cuit_con_guiones():
    url = generar_qr_url(
        cuit="20-00000000-1",
        pto_vta=1,
        tipo_cmp=6,
        nro_cmp=1,
        importe=Decimal("100"),
        cae="11111111111111",
        fecha=date.today(),
        tipo_doc_rec=99,
        nro_doc_rec="0",
    )
    encoded = url.split("?p=", 1)[1]
    pad = "=" * (-len(encoded) % 4)
    payload = json.loads(base64.urlsafe_b64decode(encoded + pad))
    # Guiones filtrados: 20000000001
    assert payload["cuit"] == 20000000001


def test_generar_qr_url_consumidor_final_sin_doc():
    """CF anonimo: nro_doc="0" (string) debe serializarse como int 0."""
    url = generar_qr_url(
        cuit="20000000001",
        pto_vta=1,
        tipo_cmp=6,
        nro_cmp=1,
        importe=Decimal("100"),
        cae="11111111111111",
        fecha=date.today(),
        tipo_doc_rec=99,
        nro_doc_rec="",
    )
    encoded = url.split("?p=", 1)[1]
    pad = "=" * (-len(encoded) % 4)
    payload = json.loads(base64.urlsafe_b64decode(encoded + pad))
    assert payload["nroDocRec"] == 0


# ------------------------------------------------------------------ Factory


def test_factory_mock_returns_mock_provider(app):
    """Con AFIP_MODE=mock (default en dev), factory devuelve MockProvider."""
    with app.app_context():
        from app.config import get_settings

        # El app fixture no toca AFIP_MODE — default es "mock".
        settings = get_settings()
        assert settings.AFIP_MODE == "mock"
        provider = get_provider()
        assert isinstance(provider, MockProvider)


def test_factory_pyafipws_fallback_to_mock_on_missing_deps(app, monkeypatch):
    """Con AFIP_MODE=pyafipws pero sin cert o sin pyafipws instalado,
    el factory cae a MockProvider con warning — NO rompe."""
    from app.config import Settings, get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("AFIP_MODE", "pyafipws")
    monkeypatch.setenv("AFIP_CERT_PATH", "")
    monkeypatch.setenv("AFIP_KEY_PATH", "")

    # Reload settings con nuevos env vars.
    get_settings.cache_clear()
    try:
        provider = get_provider()
        # Debe caer a mock porque falta cert_path.
        assert isinstance(provider, MockProvider)
    finally:
        get_settings.cache_clear()


def test_factory_disabled_raises(app, monkeypatch):
    from app.config import get_settings

    monkeypatch.setenv("AFIP_MODE", "disabled")
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="deshabilitado"):
            get_provider()
    finally:
        get_settings.cache_clear()


# ------------------------------------------------------------------ Tipos


def test_tipo_afip_map_conocidos():
    assert TIPO_AFIP_MAP["factura_a"] == 1
    assert TIPO_AFIP_MAP["factura_b"] == 6
    assert TIPO_AFIP_MAP["factura_c"] == 11
    assert TIPO_AFIP_MAP["nc_a"] == 3
    assert TIPO_AFIP_MAP["nc_b"] == 8
    assert TIPO_AFIP_MAP["nc_c"] == 13


def test_get_tipo_afip_con_default():
    assert get_tipo_afip("factura_a") == 1
    assert get_tipo_afip("no_existe", default=6) == 6


def test_get_tipo_afip_sin_default_levanta():
    with pytest.raises(KeyError):
        get_tipo_afip("definitivamente_no_existe")


def test_cond_iva_receptor_rg_5616():
    assert COND_IVA_RECEPTOR_RG_5616["responsable_inscripto"] == 1
    assert COND_IVA_RECEPTOR_RG_5616["consumidor_final"] == 5
    assert COND_IVA_RECEPTOR_RG_5616["monotributo"] == 6
    assert get_cond_iva_receptor("exento") == 4


# ------------------------------------------------------------------ PyAfipWs (skip)


@pytest.mark.skipif(
    not os.getenv("AFIP_INTEGRATION"),
    reason="test de integracion AFIP — requiere cert + AFIP_INTEGRATION=1",
)
def test_pyafipws_provider_integration():  # pragma: no cover
    """Integracion real contra AFIP homo. Setea AFIP_INTEGRATION=1 + cert+key validos."""
    from app.services.afip.pyafipws_provider import PyAfipWsProvider

    provider = PyAfipWsProvider(
        cuit=os.environ["AFIP_CUIT"],
        cert_path=os.environ["AFIP_CERT_PATH"],
        key_path=os.environ["AFIP_KEY_PATH"],
        homo=True,
    )
    ultimo = provider.ultimo_autorizado(os.environ["AFIP_CUIT"], 6, 1)
    assert isinstance(ultimo, int)
    assert ultimo >= 0
