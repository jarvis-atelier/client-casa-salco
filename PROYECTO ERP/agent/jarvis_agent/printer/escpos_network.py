"""Network printer driver — ESC/POS over TCP/IP raw printing (port 9100).

Most 3NSTAR Ethernet thermal printers (PRP-080N, etc.) listen on TCP/9100 by
default. We use python-escpos's `Network` driver, but fall back to a raw
socket implementation if python-escpos isn't available — the wire protocol is
just "open TCP socket, write ESC/POS bytes, close" so this is robust.
"""
from __future__ import annotations

import logging
import socket
import time

from ..config import Settings
from ..ticket.renderer import RenderedTicket
from .base import IPrinterDriver, PrintResult, PrinterError, PrinterStatus

log = logging.getLogger(__name__)


class NetworkPrinter(IPrinterDriver):
    """ESC/POS over TCP/IP (raw 9100)."""

    name = "network"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # ------------------------------------------------------------------
    def _connect(self, *, timeout: float = 5.0) -> socket.socket:
        try:
            sock = socket.create_connection(
                (self.settings.PRINTER_NETWORK_HOST, self.settings.PRINTER_NETWORK_PORT),
                timeout=timeout,
            )
            return sock
        except OSError as e:
            raise PrinterError(
                f"No se pudo conectar a la impresora "
                f"{self.settings.PRINTER_NETWORK_HOST}:"
                f"{self.settings.PRINTER_NETWORK_PORT} ({e})",
                code="network_connect_failed",
            ) from e

    # ------------------------------------------------------------------
    def status(self) -> PrinterStatus:
        try:
            sock = self._connect(timeout=2.0)
            sock.close()
            return PrinterStatus(
                status="ready",
                driver="network",
                model="3NSTAR ESC/POS Ethernet",
                papel="unknown",
                online=True,
                detail=(
                    f"{self.settings.PRINTER_NETWORK_HOST}:"
                    f"{self.settings.PRINTER_NETWORK_PORT}"
                ),
            )
        except PrinterError as e:
            return PrinterStatus(
                status="offline",
                driver="network",
                model="3NSTAR ESC/POS Ethernet",
                papel="unknown",
                online=False,
                detail=str(e),
            )

    # ------------------------------------------------------------------
    def print_ticket(self, rendered: RenderedTicket) -> PrintResult:
        started = time.perf_counter()
        sock = self._connect(timeout=10.0)
        try:
            sock.sendall(rendered.escpos_bytes)
        except OSError as e:
            raise PrinterError(
                f"Network write failed: {e}", code="network_write_failed"
            ) from e
        finally:
            try:
                sock.close()
            except Exception:
                pass

        log.info(
            "network printer sent %d bytes to %s:%d",
            len(rendered.escpos_bytes),
            self.settings.PRINTER_NETWORK_HOST,
            self.settings.PRINTER_NETWORK_PORT,
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        return PrintResult(printed=True, duration_ms=duration_ms, preview_id=None)
