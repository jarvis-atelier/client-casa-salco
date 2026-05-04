"""Generador de URL de QR AFIP — spec https://www.afip.gob.ar/fe/qr/.

El QR fiscal AFIP es un JSON codificado en base64 URL-safe anadido como query
param `?p=` a la URL https://www.afip.gob.ar/fe/qr/. Cualquier app lector de QR
o el visor AFIP puede validar el comprobante escaneandolo.
"""
from __future__ import annotations

import base64
import json
from datetime import date
from decimal import Decimal


def generar_qr_url(
    cuit: str,
    pto_vta: int,
    tipo_cmp: int,
    nro_cmp: int,
    importe: Decimal,
    cae: str,
    fecha: date,
    tipo_doc_rec: int,
    nro_doc_rec: str,
    moneda: str = "PES",
    cotizacion: Decimal = Decimal("1"),
) -> str:
    """Construye la URL del QR AFIP segun la spec oficial.

    Formato del payload JSON (claves ordenadas segun AFIP):
        ver: 1 (version de la spec)
        fecha: ISO-8601 yyyy-mm-dd
        cuit: CUIT emisor (int)
        ptoVta: punto de venta (int)
        tipoCmp: tipo comprobante (int, codigo AFIP)
        nroCmp: numero comprobante (int)
        importe: total (float)
        moneda: "PES" / "DOL" / etc.
        ctz: cotizacion (float)
        tipoDocRec: 80=CUIT, 96=DNI, 99=CF
        nroDocRec: numero documento receptor (int)
        tipoCodAut: "E" (CAE) o "A" (CAEA)
        codAut: el CAE (int)
    """
    cuit_clean = _limpiar_cuit(cuit)
    nro_doc_clean = _limpiar_doc(nro_doc_rec)

    payload = {
        "ver": 1,
        "fecha": fecha.isoformat(),
        "cuit": int(cuit_clean),
        "ptoVta": int(pto_vta),
        "tipoCmp": int(tipo_cmp),
        "nroCmp": int(nro_cmp),
        "importe": float(importe),
        "moneda": moneda,
        "ctz": float(cotizacion),
        "tipoDocRec": int(tipo_doc_rec),
        "nroDocRec": nro_doc_clean,
        "tipoCodAut": "E",
        "codAut": int(cae),
    }

    # AFIP espera separadores compactos (sin espacios) — obligatorio para que el QR
    # valide. No cambies estos separadores.
    json_str = json.dumps(payload, separators=(",", ":"))
    encoded = base64.urlsafe_b64encode(json_str.encode("utf-8")).decode("ascii")

    return f"https://www.afip.gob.ar/fe/qr/?p={encoded}"


def generar_qr_png(url: str, box_size: int = 10, border: int = 2) -> bytes:
    """Opcional: renderiza el QR a PNG. Requiere `qrcode[pil]` (grupo opcional 'afip').

    Si qrcode no esta instalado, levanta ImportError con mensaje claro.
    """
    try:
        import qrcode  # type: ignore
    except ImportError as err:  # pragma: no cover — depende de grupo opcional afip
        raise ImportError(
            "qrcode no esta instalado — activa el extra 'afip': "
            "pip install -e \".[afip]\""
        ) from err

    from io import BytesIO

    img = qrcode.make(url, box_size=box_size, border=border)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _limpiar_cuit(cuit: str) -> str:
    """CUIT puede venir con guiones '20-12345678-9' o sin ellos. Retorna solo digitos."""
    return "".join(ch for ch in cuit if ch.isdigit())


def _limpiar_doc(doc: str) -> int:
    """Documento receptor. Puede ser DNI, CUIT, o "0" si es CF sin identificar."""
    clean = "".join(ch for ch in str(doc) if ch.isdigit())
    return int(clean) if clean else 0
