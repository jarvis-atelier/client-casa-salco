"""Factory — selecciona el provider AFIP segun la config.

Regla: `settings.AFIP_MODE` manda.
    - "mock"     -> MockProvider (dev, testing, CI)
    - "pyafipws" -> PyAfipWsProvider (prod). Si falla import o falta cert,
                    cae a mock con un warning en log — NUNCA rompe la app.
    - "disabled" -> lanza RuntimeError. Usalo en tests que explicitamente
                    quieren validar que AFIP no esta activo.
"""
from __future__ import annotations

import logging

from app.config import get_settings

from .base import FiscalInvoiceProvider, ProviderUnavailableError
from .mock import MockProvider

logger = logging.getLogger(__name__)


def get_provider() -> FiscalInvoiceProvider:
    """Retorna la instancia del provider configurada. NUNCA retorna None."""
    settings = get_settings()

    if settings.AFIP_MODE == "disabled":
        raise RuntimeError(
            "AFIP esta deshabilitado en este entorno (AFIP_MODE=disabled). "
            "Revisa tu .env o la config de test."
        )

    if settings.AFIP_MODE == "mock":
        return MockProvider()

    if settings.AFIP_MODE == "pyafipws":
        try:
            # Import lazy — asi si pyafipws no esta instalado no rompe el import
            # de este modulo en CI / dev sin afip extras.
            from .pyafipws_provider import PyAfipWsProvider

            return PyAfipWsProvider(
                cuit=settings.AFIP_CUIT,
                cert_path=settings.AFIP_CERT_PATH,
                key_path=settings.AFIP_KEY_PATH,
                homo=settings.AFIP_HOMO,
            )
        except ProviderUnavailableError as exc:
            logger.warning(
                "PyAfipWsProvider no disponible (%s). Fallback a MockProvider. "
                "NO USAR EN PRODUCCION.",
                exc,
            )
            return MockProvider()

    raise ValueError(f"AFIP_MODE invalido: {settings.AFIP_MODE!r}")
