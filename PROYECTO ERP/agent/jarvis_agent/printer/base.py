"""Abstract printer driver interface + status / error types."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from ..ticket.renderer import RenderedTicket


class PrinterError(Exception):
    """Raised by drivers when the physical printer can't accept the job.

    The HTTP layer maps this to 502 with the message in the body.
    """

    def __init__(self, message: str, *, code: str = "printer_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class PrinterStatus:
    """Runtime status returned by `IPrinterDriver.status()`."""

    status: Literal["ready", "error", "offline", "no_paper"]
    driver: Literal["mock", "usb", "network"]
    model: str = "unknown"
    papel: Literal["ok", "low", "out", "unknown"] = "unknown"
    online: bool = True
    detail: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class PrintResult:
    """Returned by `IPrinterDriver.print_ticket()`."""

    printed: bool
    preview_id: str | None = None
    duration_ms: int = 0
    detail: str | None = None


class IPrinterDriver(ABC):
    """Abstract printer driver."""

    name: Literal["mock", "usb", "network"] = "mock"

    @abstractmethod
    def status(self) -> PrinterStatus:
        """Return current driver/printer status — must NOT raise."""

    @abstractmethod
    def print_ticket(self, rendered: RenderedTicket) -> PrintResult:
        """Send the rendered ticket to the printer.

        On hardware error, raise `PrinterError` (the API translates to 502).
        """
