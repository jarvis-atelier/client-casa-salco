"""Servicio de facturacion electronica AFIP / ARCA.

Expone una interfaz `FiscalInvoiceProvider` con dos implementaciones:

- `MockProvider`: genera CAE deterministico para dev/testing sin tocar AFIP.
- `PyAfipWsProvider`: cliente real WSFEv1 via pyafipws (prod).

Elegi el provider via `get_provider()` segun `settings.AFIP_MODE`.
"""
from .base import (
    AfipFacturaInput,
    AfipFacturaOutput,
    FiscalInvoiceProvider,
    ProviderUnavailableError,
)
from .factory import get_provider
from .mock import MockProvider
from .qr import generar_qr_url
from .tipos import COND_IVA_RECEPTOR_RG_5616, TIPO_AFIP_MAP

__all__ = [
    "COND_IVA_RECEPTOR_RG_5616",
    "AfipFacturaInput",
    "AfipFacturaOutput",
    "FiscalInvoiceProvider",
    "MockProvider",
    "ProviderUnavailableError",
    "TIPO_AFIP_MAP",
    "generar_qr_url",
    "get_provider",
]
