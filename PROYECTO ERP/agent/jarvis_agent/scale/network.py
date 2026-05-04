"""Network scale driver — TCP/IP raw socket.

Some modern Kretz/Systel models ship an Ethernet card (or a Moxa-style
serial-to-ethernet bridge) that exposes the scale's serial protocol over a
TCP socket, typically on port 1001 or 4001. The wire format is the same as
the serial drivers; we just swap `pyserial` for `socket`.

Useful when:
- The scale is far from the cashier PC (no long RS-232 run).
- You're consolidating several scales onto one server.
- The site already has a Moxa NPort or USR-TCP-COM bridge installed.

Same protocol assumptions and parser as `kretz.py` / `systel.py`.
"""
from __future__ import annotations

import logging
import socket
import time
from datetime import datetime
from decimal import Decimal

from .base import IScaleDriver, ScaleError, ScaleStatus, WeightReading
from ._serial_common import is_stable_marker, parse_weight_line

log = logging.getLogger(__name__)


class NetworkScale(IScaleDriver):
    """TCP/IP scale driver — speaks the same Kretz/Systel-style serial frames
    but over a socket instead of a COM port.
    """

    name = "network"

    def __init__(
        self,
        host: str,
        port: int = 1001,
        *,
        timeout: float = 1.0,
    ) -> None:
        self._host = host
        self._port = port
        self._timeout = timeout
        self._sock: socket.socket | None = None
        self._tare_kg: Decimal = Decimal("0.000")
        self._last_weight: Decimal | None = None
        self._last_error: str | None = None

    # ------------------------------------------------------------------
    def _ensure_open(self) -> socket.socket:
        if self._sock is not None:
            return self._sock
        try:
            s = socket.create_connection((self._host, self._port), timeout=self._timeout)
            s.settimeout(self._timeout)
            self._sock = s
            return s
        except OSError as exc:
            raise ScaleError(
                f"no se pudo conectar a {self._host}:{self._port} ({exc})",
                code="net_connect_failed",
            ) from exc

    # ------------------------------------------------------------------
    def _read_frames(self, max_bytes: int = 256) -> list[str]:
        if self._sock is None:
            return []
        deadline = time.monotonic() + self._timeout
        buf = bytearray()
        while time.monotonic() < deadline and len(buf) < max_bytes:
            try:
                chunk = self._sock.recv(64)
            except socket.timeout:
                break
            except OSError as exc:
                self._last_error = f"recv error: {exc}"
                break
            if not chunk:
                break
            buf.extend(chunk)
            if b"\n" in chunk or b"\r" in chunk:
                # Got at least one complete frame — keep draining briefly.
                deadline = min(deadline, time.monotonic() + 0.05)
        text = buf.decode("ascii", errors="ignore")
        # Split on CR/LF/STX/ETX, keep non-empty.
        parts = [
            p.strip(" \t\x02\x03")
            for p in text.replace("\r", "\n").split("\n")
            if p.strip()
        ]
        return parts

    # ------------------------------------------------------------------
    def get_weight(self) -> WeightReading:
        s = self._ensure_open()
        try:
            s.sendall(b"P\r")
        except OSError as exc:
            # Socket likely dropped — close + raise so a retry reopens it.
            self.close()
            raise ScaleError(
                f"send fallo a {self._host}:{self._port} ({exc})", code="net_send_failed"
            ) from exc

        lines = self._read_frames()
        if not lines:
            self._last_error = "sin respuesta"
            raise ScaleError(
                f"balanza network {self._host}:{self._port} no respondió",
                code="no_response",
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
            "balanza network envió frames pero ninguno con peso reconocible",
            code="parse_failed",
        )

    # ------------------------------------------------------------------
    def tare(self) -> bool:
        try:
            s = self._ensure_open()
            s.sendall(b"T\r")
            if self._last_weight is not None:
                self._tare_kg = self._last_weight
            return True
        except (OSError, ScaleError) as exc:
            log.warning("network scale tare failed: %s", exc)
            self._last_error = f"tare error: {exc}"
            return False

    # ------------------------------------------------------------------
    def status(self) -> ScaleStatus:
        online = self._sock is not None
        return ScaleStatus(
            status="ready" if online else "offline",
            driver="network",
            model=f"network scale {self._host}:{self._port}",
            online=online,
            port=f"{self._host}:{self._port}",
            last_weight_kg=self._last_weight,
            detail="TCP raw socket — protocolo serial sobre red",
            error=self._last_error,
        )

    # ------------------------------------------------------------------
    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:  # pragma: no cover
                pass
            self._sock = None
