"""Provider Google Gemini Vision — extraccion real de comprobantes.

Modelo recomendado: gemini-1.5-flash (ultrabarato, ~$0.075/1M tokens, free tier amplio).
Tambien soporta gemini-1.5-pro si se quiere mas calidad a mayor costo.
"""
from __future__ import annotations

import io
import json
import logging
from typing import Any

from . import OcrExtractionError, OcrProvider

logger = logging.getLogger(__name__)

PROMPT = """Sos un asistente que extrae datos de comprobantes comerciales argentinos
(facturas A/B/C, remitos, presupuestos). Te paso una imagen del comprobante.

Devolve un JSON con esta estructura EXACTA:
{
  "tipo": "factura" | "remito" | "presupuesto" | "desconocido",
  "letra": "A" | "B" | "C" | null,
  "proveedor": {
    "razon_social": string | null,
    "cuit": string | null
  },
  "numero_comprobante": string | null,
  "fecha": string | null,
  "items": [
    {
      "descripcion": string,
      "cantidad": number,
      "unidad": "unidad" | "kg" | "gr" | "lt" | "ml",
      "precio_unitario": string,
      "subtotal": string
    }
  ],
  "subtotal": string | null,
  "iva_total": string | null,
  "total": string | null,
  "confianza": number
}

REGLAS:
- Si la imagen esta borrosa o no es un comprobante, devolve tipo "desconocido" y confianza baja.
- Si no estas seguro de un campo, devolve null.
- Decimales con punto, no coma.
- Fecha en formato ISO YYYY-MM-DD.
- CUIT en formato XX-XXXXXXXX-X cuando sea posible.
- NO INVENTES. Mejor null que mal.
- Responde SOLO con el JSON, sin texto adicional, sin bloque markdown."""

MAX_BYTES = 5 * 1024 * 1024


def _maybe_resize(image_bytes: bytes, mime: str) -> tuple[bytes, str]:
    """Si la imagen pesa > 5MB intenta reducirla con Pillow."""
    if len(image_bytes) <= MAX_BYTES:
        return image_bytes, mime
    if not mime.startswith("image/"):
        return image_bytes, mime
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        max_side = 1600
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side))
        out = io.BytesIO()
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out, format="JPEG", quality=82, optimize=True)
        return out.getvalue(), "image/jpeg"
    except Exception:  # pragma: no cover
        logger.warning("No pude redimensionar la imagen, mando original")
        return image_bytes, mime


def _normalize_mime(mime: str) -> str:
    """Gemini acepta image/jpeg, image/png, image/webp, image/heic, image/heif, application/pdf."""
    if mime in {"image/jpeg", "image/png", "image/webp", "image/heic", "image/heif", "application/pdf"}:
        return mime
    return "image/jpeg"


class GeminiVisionProvider(OcrProvider):
    """Provider que usa la SDK oficial de Google Generative AI con Gemini Vision."""

    name = "gemini"

    def __init__(self, api_key: str, model: str = "gemini-1.5-flash"):
        try:
            import google.generativeai as genai
        except ImportError as exc:  # pragma: no cover
            raise OcrExtractionError(
                "Falta la dependencia 'google-generativeai'. Instala con extras [ocr]."
            ) from exc

        genai.configure(api_key=api_key)
        self._genai = genai
        self.model_name = model
        self.model = genai.GenerativeModel(model)

    def extract(self, image_bytes: bytes, mime: str) -> dict[str, Any]:
        image_bytes, mime = _maybe_resize(image_bytes, mime)
        mime = _normalize_mime(mime)

        # Gemini acepta inline_data con mime + bytes en base64. La SDK lo abstrae con
        # un dict {"mime_type": ..., "data": bytes}.
        try:
            resp = self.model.generate_content(
                [
                    {"mime_type": mime, "data": image_bytes},
                    PROMPT,
                ],
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 2048,
                    "response_mime_type": "application/json",
                },
            )
        except Exception as exc:  # pragma: no cover
            raise OcrExtractionError(f"falla en Gemini API: {exc}") from exc

        text = (resp.text or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json\n"):
                text = text[5:]

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise OcrExtractionError(
                f"respuesta no es JSON valido: {text[:200]}"
            ) from exc

        data.setdefault("tipo", "desconocido")
        data.setdefault("items", [])
        data.setdefault("confianza", 0.5)
        data["modelo"] = self.model_name
        data["raw_response"] = {"provider": "gemini", "model": self.model_name}
        return data
