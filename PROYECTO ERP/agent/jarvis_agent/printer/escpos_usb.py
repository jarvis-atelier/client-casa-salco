"""USB printer driver for 3NSTAR ESC/POS thermal printers (e.g. PRP-080).

Note on Windows: pyusb depends on libusb-win32 / libusbK / WinUSB. Most 3NSTAR
USB printers ship with a Windows print driver that masks the raw USB endpoint;
to use this driver you typically need to install libusb-win32 with Zadig and
pick the printer's USB device. Otherwise prefer the Network driver (TCP 9100)
or use the mock driver.

If pyusb fails to find / open the device, this driver raises `PrinterError`
with a clear message. It NEVER falls back silently.
"""
from __future__ import annotations

import logging
import time

from ..config import Settings
from ..ticket.renderer import RenderedTicket
from .base import IPrinterDriver, PrintResult, PrinterError, PrinterStatus

log = logging.getLogger(__name__)


class UsbPrinter(IPrinterDriver):
    """ESC/POS over USB — uses python-escpos `Usb` driver."""

    name = "usb"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._last_status: str = "unknown"

    # ------------------------------------------------------------------
    def _open(self):  # type: ignore[no-untyped-def]
        """Open the USB device. Returns the python-escpos Usb instance."""
        try:
            from escpos.printer import Usb
        except ImportError as e:  # pragma: no cover
            raise PrinterError(
                "python-escpos no instalado — instalá con `pip install python-escpos`",
                code="dep_missing",
            ) from e

        try:
            return Usb(
                idVendor=self.settings.PRINTER_USB_VENDOR,
                idProduct=self.settings.PRINTER_USB_PRODUCT,
                interface=self.settings.PRINTER_USB_INTERFACE,
                in_ep=self.settings.PRINTER_USB_IN_EP,
                out_ep=self.settings.PRINTER_USB_OUT_EP,
            )
        except Exception as e:  # pyusb / escpos can raise many things
            raise PrinterError(
                f"No se pudo abrir la impresora USB "
                f"(vendor=0x{self.settings.PRINTER_USB_VENDOR:04x} "
                f"product=0x{self.settings.PRINTER_USB_PRODUCT:04x}): {e}",
                code="usb_open_failed",
            ) from e

    # ------------------------------------------------------------------
    def status(self) -> PrinterStatus:
        try:
            dev = self._open()
            # Best-effort close — escpos doesn't always provide a clean close API
            try:
                dev.close()
            except Exception:
                pass
            self._last_status = "ready"
            return PrinterStatus(
                status="ready",
                driver="usb",
                model="3NSTAR ESC/POS USB",
                papel="unknown",
                online=True,
                detail=(
                    f"vendor=0x{self.settings.PRINTER_USB_VENDOR:04x} "
                    f"product=0x{self.settings.PRINTER_USB_PRODUCT:04x}"
                ),
            )
        except PrinterError as e:
            self._last_status = "error"
            return PrinterStatus(
                status="offline",
                driver="usb",
                model="3NSTAR ESC/POS USB",
                papel="unknown",
                online=False,
                detail=str(e),
            )

    # ------------------------------------------------------------------
    def print_ticket(self, rendered: RenderedTicket) -> PrintResult:
        started = time.perf_counter()
        dev = self._open()
        try:
            dev._raw(rendered.escpos_bytes)  # python-escpos low-level send
        except Exception as e:
            raise PrinterError(f"USB write failed: {e}", code="usb_write_failed") from e
        finally:
            try:
                dev.close()
            except Exception:
                pass

        log.info(
            "usb printer sent %d bytes for ticket %s",
            len(rendered.escpos_bytes),
            rendered.metadata.get("numero"),
        )
        duration_ms = int((time.perf_counter() - started) * 1000)
        return PrintResult(printed=True, duration_ms=duration_ms, preview_id=None)
