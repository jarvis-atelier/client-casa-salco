"""Printer driver selector — picks driver based on settings."""
from __future__ import annotations

import logging

from ..config import Settings, get_settings
from .base import IPrinterDriver

log = logging.getLogger(__name__)


def get_printer(settings: Settings | None = None) -> IPrinterDriver:
    """Return the configured `IPrinterDriver` (mock | usb | network).

    On import errors of the requested backend, falls back to MockPrinter with a
    loud warning — the agent is still usable for development.
    """
    settings = settings or get_settings()
    mode = settings.PRINTER_MODE

    if mode == "mock":
        from .mock import MockPrinter

        return MockPrinter()

    if mode == "usb":
        try:
            from .escpos_usb import UsbPrinter

            return UsbPrinter(settings)
        except Exception as e:  # pragma: no cover
            log.warning("USB driver unavailable (%s) — falling back to mock", e)
            from .mock import MockPrinter

            return MockPrinter()

    if mode == "network":
        try:
            from .escpos_network import NetworkPrinter

            return NetworkPrinter(settings)
        except Exception as e:  # pragma: no cover
            log.warning("Network driver unavailable (%s) — falling back to mock", e)
            from .mock import MockPrinter

            return MockPrinter()

    raise ValueError(f"PRINTER_MODE invalido: {mode}")
