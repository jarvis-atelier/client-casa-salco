"""Provider mock — determinístico, sin API call, útil para dev/test sin key."""
from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from . import OcrProvider


_BASE_ITEMS = [
    {"descripcion": "Coca Cola 2.25L", "cantidad": 12, "unidad": "unidad",
     "precio_unitario": "1850.00"},
    {"descripcion": "Arroz Gallo 1kg", "cantidad": 24, "unidad": "unidad",
     "precio_unitario": "920.00"},
    {"descripcion": "Aceite Cocinero 1.5L", "cantidad": 6, "unidad": "unidad",
     "precio_unitario": "3450.00"},
    {"descripcion": "Pan rallado 500g", "cantidad": 10, "unidad": "unidad",
     "precio_unitario": "780.00"},
    {"descripcion": "Yerba Rosamonte 1kg", "cantidad": 8, "unidad": "unidad",
     "precio_unitario": "2640.00"},
]


class MockProvider(OcrProvider):
    """Devuelve un comprobante fake derivado del hash de los bytes.

    No llama a ninguna API externa. Es determinístico: dada la misma imagen,
    siempre devuelve los mismos datos. Útil para tests y para ambiente sin key.
    """

    name = "mock"

    def extract(self, image_bytes: bytes, mime: str) -> dict[str, Any]:  # noqa: ARG002
        h = hashlib.sha256(image_bytes).hexdigest()
        # 3-5 items según hash
        seed = int(h[:6], 16)
        cantidad_items = 3 + (seed % 3)  # 3,4,5
        items = []
        subtotal_total = 0.0
        for i in range(cantidad_items):
            base = _BASE_ITEMS[(seed + i) % len(_BASE_ITEMS)]
            cantidad = float(base["cantidad"])
            precio = float(base["precio_unitario"])
            sub = round(cantidad * precio, 2)
            items.append(
                {
                    "descripcion": base["descripcion"],
                    "cantidad": cantidad,
                    "unidad": base["unidad"],
                    "precio_unitario": f"{precio:.2f}",
                    "subtotal": f"{sub:.2f}",
                }
            )
            subtotal_total += sub

        iva = round(subtotal_total * 0.21, 2)
        total = round(subtotal_total + iva, 2)
        cuit_seed = h[:11]
        cuit = (
            f"30-{cuit_seed[1:9].translate(str.maketrans('abcdef', '012345'))}-{int(h[12], 16) % 10}"
        )

        return {
            "tipo": "factura",
            "letra": "A",
            "proveedor": {
                "razon_social": "Distribuidora Mock SA",
                "cuit": cuit,
            },
            "numero_comprobante": f"0001-{(seed % 100000):08d}",
            "fecha": date.today().isoformat(),
            "items": items,
            "subtotal": f"{subtotal_total:.2f}",
            "iva_total": f"{iva:.2f}",
            "total": f"{total:.2f}",
            "confianza": 0.85,
            "modelo": "mock",
            "raw_response": {"provider": "mock", "hash": h},
        }
