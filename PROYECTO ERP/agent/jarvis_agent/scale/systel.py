"""Systel scale driver (serial COM).

Systel models commonly seen in Argentine grocery counters: Croma, Aspen, Mensa,
Volar. Like Kretz, the wire protocol depends on the firmware: most ship with
9600 8N1 RS-232, continuous-send by default, with a frame layout roughly:

    "+1.234kg<CR><LF>"
    "ST GS 0001.234 kg"
    "<STX>+1234.5g<ETX>"

Some Systel firmwares respond to ASCII commands:

    "P\r"   → request weight
    "T\r"   → tare
    "Z\r"   → zero (set platter as origin, not the same as tare)

We use a flexible regex parser (shared with the Kretz driver) so the same
implementation handles continuous and polled modes. If the parser misses
something specific to your model, extend the regex in `_serial_common`.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from decimal import Decimal

from .base import IScaleDriver, ScaleError, ScaleStatus, WeightReading
from ._serial_common import (
    is_stable_marker,
    open_serial,
    parse_weight_line,
    read_lines,
)

log = logging.getLogger(__name__)


class SystelScale(IScaleDriver):
    """Systel serial scale driver."""

    name = "systel"

    def __init__(
        self,
        port: str,
        *,
        baudrate: int = 9600,
        timeout: float = 1.0,
    ) -> None:
        self._port = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._serial = None
        self._tare_kg: Decimal = Decimal("0.000")
        self._last_weight: Decimal | None = None
        self._last_error: str | None = None

    # ------------------------------------------------------------------
    def _ensure_open(self):  # type: ignore[no-untyped-def]
        if self._serial is not None and getattr(self._serial, "is_open", False):
            return self._serial
        self._serial = open_serial(self._port, self._baudrate, self._timeout)
        try:
            self._serial.reset_input_buffer()
        except Exception:  # pragma: no cover
            pass
        return self._serial

    # ------------------------------------------------------------------
    def _send_poll(self) -> None:
        """Ask Systel for a weight frame. No-op on continuous firmware."""
        if self._serial is None:
            return
        try:
            self._serial.reset_input_buffer()
            self._serial.write(b"P\r")
            self._serial.flush()
            time.sleep(0.05)
        except Exception as exc:
            log.debug("systel poll failed: %s", exc)

    # ------------------------------------------------------------------
    def get_weight(self) -> WeightReading:
        ser = self._ensure_open()
        self._send_poll()

        lines = read_lines(ser, max_lines=6)
        if not lines:
            self._last_error = "sin respuesta"
            raise ScaleError(
                f"Systel no respondió en {self._port}", code="no_response"
            )

        for line in lines:
            parsed = parse_weight_line(line, default_unit="kg")
            if not parsed:
                continue
            kg, unit = parsed
            stable = is_stable_marker(line)
            self._last_weight = kg
            self._last_error = None
            return WeightReading(
                weight_kg=kg,
                stable=stable,
                tare_kg=self._tare_kg,
                unit="kg" if unit == "kg" else "g",
                timestamp=datetime.now(),
                raw_response=line,
            )

        self._last_error = f"frames sin peso reconocible: {lines!r}"
        raise ScaleError(
            "Systel envió frames pero ninguno con peso reconocible",
            code="parse_failed",
        )

    # ------------------------------------------------------------------
    def tare(self) -> bool:
        ser = self._ensure_open()
        try:
            ser.write(b"T\r")
            ser.flush()
            if self._last_weight is not None:
                self._tare_kg = self._last_weight
            return True
        except Exception as exc:
            log.warning("systel tare failed: %s", exc)
            self._last_error = f"tare error: {exc}"
            return False

    # ------------------------------------------------------------------
    def status(self) -> ScaleStatus:
        online = self._serial is not None and getattr(self._serial, "is_open", False)
        return ScaleStatus(
            status="ready" if online else "offline",
            driver="systel",
            model="Systel (serial)",
            online=online,
            port=self._port,
            last_weight_kg=self._last_weight,
            detail=f"{self._port} @ {self._baudrate} 8N1",
            error=self._last_error,
        )

    # ------------------------------------------------------------------
    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            except Exception:  # pragma: no cover
                pass
            self._serial = None
