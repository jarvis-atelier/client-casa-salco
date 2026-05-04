"""Servicio OCR — extracción de comprobantes vía Claude Vision (o mock)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class OcrExtractionError(Exception):
    """Error genérico durante la extracción OCR."""


class OcrProvider(ABC):
    """Contrato común para todos los providers de OCR.

    El provider recibe los bytes crudos de la imagen y devuelve un dict con la
    estructura especificada en el prompt (tipo, proveedor, items, totales,
    confianza, raw_response, modelo).
    """

    name: str = "abstract"

    @abstractmethod
    def extract(self, image_bytes: bytes, mime: str) -> dict[str, Any]:
        """Devuelve un dict normalizado con la información del comprobante.

        Estructura mínima:
            {
                "tipo": "factura" | "remito" | "presupuesto" | "desconocido",
                "letra": "A" | "B" | "C" | None,
                "proveedor": {"razon_social": str|None, "cuit": str|None},
                "numero_comprobante": str | None,
                "fecha": str | None,  # ISO YYYY-MM-DD
                "items": [
                    {"descripcion", "cantidad", "unidad",
                     "precio_unitario", "subtotal"}
                ],
                "subtotal": str | None,
                "iva_total": str | None,
                "total": str | None,
                "confianza": float,
                "modelo": str,
                "raw_response": dict,  # libre, para auditoria
            }
        """
        raise NotImplementedError


__all__ = ["OcrProvider", "OcrExtractionError"]
