"""Servicios del módulo Calendario de pagos.

`pagos_service` — registrar pagos contra compromisos, marcar estados, integrar
con el ledger de caja.

`auto_generar` — generar compromisos automáticamente desde facturas tipo C
nuevas y desde resúmenes de tarjeta del mes.
"""
from .auto_generar import auto_generar_compromisos
from .pagos_service import (
    CompromisoValidationError,
    aplicar_pago,
    refrescar_estado,
)

__all__ = [
    "CompromisoValidationError",
    "aplicar_pago",
    "auto_generar_compromisos",
    "refrescar_estado",
]
