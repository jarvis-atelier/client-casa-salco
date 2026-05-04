"""Kretz scale driver (serial COM).

Kretz is the dominant retail scale brand in Argentina. Common counter models
(Aqua, Aqua II, Aria-XS, Carro) ship with an RS-232 / TTL serial port. The
PROTOCOL VARIES per firmware revision — some models stream a continuous frame
every ~250 ms, others only respond to a `P` polling command, and a handful
use STX/ETX framing. Rather than hard-code one version, we:

  1. Open the port with the typical 9600 8N1 defaults.
  2. Send a benign poll command (`P\r`) — it's a no-op on continuous-send
     firmware and a "give me a frame" trigger on polled firmware.
  3. Read up to N lines and run a flexible regex over each looking for the
     first plausible weight token.

Examples of frames seen in the wild (sample from Kretz docs / sniffed serial):

    "ST,GS,+0001.234kg"          # Aqua-class continuous send
    "01,P:1.234,T:0.000,N:1.234" # older Aria firmware
    "+ 1.234 kg ST"              # generic 6-digit format
    " 12345 "                    # 5-digit grams (no unit, no decimal)

If you have a Kretz model whose protocol doesn't match the regex, the right
fix is usually adding a tiny preprocessor in `_serial_common.parse_weight_line`
rather than rewriting this driver. Patches welcome.
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


class KretzScale(IScaleDriver):
    """Kretz serial scale driver."""

    name = "kretz"

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
        self._serial = None  # opened lazily so a missing COM doesn't crash boot
        self._tare_kg: Decimal = Decimal("0.000")
        self._last_weight: Decimal | None = None
        self._last_error: str | None = None

    # ------------------------------------------------------------------
    def _ensure_open(self):  # type: ignore[no-untyped-def]
        if self._serial is not None and getattr(self._serial, "is_open", False):
            return self._serial
        self._serial = open_serial(self._port, self._baudrate, self._timeout)
        # Clear any stale frames from the buffer.
        try:
            self._serial.reset_input_buffer()
        except Exception:  # pragma: no cover
            pass
        return self._serial

    # ------------------------------------------------------------------
    def _send_poll(self) -> None:
        """Trigger the scale to emit one frame.

        On continuous-send firmware this is harmless. On polled firmware it's
        required. Some Kretz models accept `P` (peso), some `<STX>P<ETX>`,
        some need `\r` only — try the most common first.
        """
        if self._serial is None:
            return
        try:
            self._serial.reset_input_buffer()
            self._serial.write(b"P\r")
            self._serial.flush()
            time.sleep(0.05)
        except Exception as exc:
            log.debug("kretz poll failed: %s", exc)

    # ------------------------------------------------------------------
    def get_weight(self) -> WeightReading:
        ser = self._ensure_open()
        self._send_poll()

        lines = read_lines(ser, max_lines=6)
        if not lines:
            self._last_error = "sin respuesta"
            raise ScaleError(
                f"Kretz no respondió en {self._port}", code="no_response"
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
            "Kretz envió frames pero ninguno con peso reconocible",
            code="parse_failed",
        )

    # ------------------------------------------------------------------
    def tare(self) -> bool:
        """Send the tare command. Most Kretz firmwares accept `T\r`."""
        ser = self._ensure_open()
        try:
            ser.write(b"T\r")
            ser.flush()
            # Update local tare estimate; the scale may also re-emit a frame.
            if self._last_weight is not None:
                self._tare_kg = self._last_weight
            return True
        except Exception as exc:
            log.warning("kretz tare failed: %s", exc)
            self._last_error = f"tare error: {exc}"
            return False

    # ------------------------------------------------------------------
    def status(self) -> ScaleStatus:
        online = self._serial is not None and getattr(self._serial, "is_open", False)
        return ScaleStatus(
            status="ready" if online else "offline",
            driver="kretz",
            model="Kretz (serial)",
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
