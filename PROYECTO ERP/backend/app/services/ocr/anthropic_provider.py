"""Provider Anthropic Claude Vision — extracción real de comprobantes."""
from __future__ import annotations

import base64
import io
import json
import logging
from typing import Any

from . import OcrExtractionError, OcrProvider

logger = logging.getLogger(__name__)

PROMPT = """Sos un asistente que extrae datos de comprobantes comerciales argentinos
(facturas A/B/C, remitos, presupuestos). Te paso una imagen del comprobante.

Devolvé un JSON con esta estructura EXACTA:
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
- Si la imagen está borrosa o no es un comprobante, devolvé tipo "desconocido" y confianza baja.
- Si no estás seguro de un campo, devolvé null.
- Decimales con punto, no coma.
- Fecha en formato ISO YYYY-MM-DD.
- CUIT en formato XX-XXXXXXXX-X cuando sea posible.
- NO INVENTES. Mejor null que mal.
- Respondé SOLO con el JSON, sin texto adicional, sin bloque markdown."""

MAX_BYTES = 5 * 1024 * 1024


def _maybe_resize(image_bytes: bytes, mime: str) -> tuple[bytes, str]:
    """Si la imagen pesa > 5MB intenta reducirla con Pillow."""
    if len(image_bytes) <= MAX_BYTES:
        return image_bytes, mime
    if not mime.startswith("image/"):
        # PDFs no se reducen aquí; los pasamos como están.
        return image_bytes, mime
    try:
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        # Bajamos calidad y resolución
        max_side = 1600
        if max(img.size) > max_side:
            img.thumbnail((max_side, max_side))
        out = io.BytesIO()
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(out, format="JPEG", quality=82, optimize=True)
        return out.getvalue(), "image/jpeg"
    except Exception:  # pragma: no cover — defensivo
        logger.warning("No pude redimensionar la imagen, mando original")
        return image_bytes, mime


class AnthropicVisionProvider(OcrProvider):
    """Provider que usa la SDK oficial de Anthropic con Claude vision."""

    name = "anthropic"

    def __init__(self, api_key: str, model: str = "claude-3-5-sonnet-20241022"):
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover
            raise OcrExtractionError(
                "Falta la dependencia 'anthropic'. Instalá con extras [ocr]."
            ) from exc

        self.client = Anthropic(api_key=api_key)
        self.model = model

    def extract(self, image_bytes: bytes, mime: str) -> dict[str, Any]:
        image_bytes, mime = _maybe_resize(image_bytes, mime)

        if mime == "application/pdf":
            # Anthropic acepta PDFs en algunos modelos. Por simplicidad,
            # intentamos pasarlo como documento. Si falla → error.
            content_blocks = [
                {
                    "type": "document",
                    "source": {
                        "type": "base64",
                        "media_type": "application/pdf",
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                    },
                },
                {"type": "text", "text": PROMPT},
            ]
        else:
            content_blocks = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": mime if mime in {"image/jpeg", "image/png", "image/webp", "image/gif"} else "image/jpeg",
                        "data": base64.b64encode(image_bytes).decode("ascii"),
                    },
                },
                {"type": "text", "text": PROMPT},
            ]

        try:
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                messages=[{"role": "user", "content": content_blocks}],
            )
        except Exception as exc:  # pragma: no cover — depende del SDK
            raise OcrExtractionError(f"falla en Anthropic API: {exc}") from exc

        # La respuesta es texto plano JSON.
        try:
            text_blocks = [b.text for b in resp.content if getattr(b, "type", "") == "text"]
        except Exception:  # pragma: no cover
            text_blocks = []
        text = "\n".join(text_blocks).strip()
        if text.startswith("```"):
            # Por si vino envuelto en bloque markdown.
            text = text.strip("`")
            if text.startswith("json\n"):
                text = text[5:]

        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise OcrExtractionError(
                f"respuesta no es JSON válido: {text[:200]}"
            ) from exc

        data.setdefault("tipo", "desconocido")
        data.setdefault("items", [])
        data.setdefault("confianza", 0.5)
        data["modelo"] = self.model
        data["raw_response"] = {"provider": "anthropic", "model": self.model}
        return data
