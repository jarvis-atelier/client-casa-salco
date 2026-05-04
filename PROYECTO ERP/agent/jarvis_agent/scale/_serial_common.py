"""Shared helpers for serial-based scale drivers (Kretz, Systel).

Both protocols vary by firmware revision but they share enough plumbing —
opening a serial port with sane defaults, retrying a "drain" read, parsing a
weight number out of a free-form line — that we factor it out here.
"""
from __future__ import annotations

import logging
import re
import time
from decimal import Decimal, InvalidOperation
from typing import TYPE_CHECKING

from .base import ScaleError

if TYPE_CHECKING:  # pragma: no cover
    import serial as _serial_mod  # type: ignore[import-not-found]

log = logging.getLogger(__name__)


def open_serial(
    port: str,
    baudrate: int,
    timeout: float,
):  # type: ignore[no-untyped-def]
    """Open the serial port with 8N1 defaults common to retail scales.

    Raises `ScaleError` if `pyserial` isn't installed or the port can't be
    opened (wrong COM, scale powered off, cable unplugged, permissions, etc).
    """
    try:
        import serial  # type: ignore[import-not-found]
    except ImportError as exc:  # pragma: no cover - depends on env
        raise ScaleError(
            "pyserial no instalado — agregá `pyserial>=3.5` a las dependencias",
            code="missing_dependency",
        ) from exc

    try:
        return serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=timeout,
            write_timeout=timeout,
        )
    except Exception as exc:  # pragma: no cover - depends on hardware
        raise ScaleError(
            f"no se pudo abrir el puerto serial {port} ({exc})",
            code="serial_open_failed",
        ) from exc


def read_lines(ser: "_serial_mod.Serial", *, max_lines: int = 8) -> list[str]:
    """Read up to `max_lines` newline-delimited frames from the scale.

    Some scales transmit continuously (every 100–250 ms), some only respond
    when prompted. We read whatever's already in the buffer plus a short
    blocking wait. Returns the decoded ASCII strings (one per line, empty
    lines stripped).
    """
    out: list[str] = []
    deadline = time.monotonic() + (ser.timeout or 1.0)

    while len(out) < max_lines and time.monotonic() < deadline:
        raw = ser.readline()
        if not raw:
            break
        try:
            text = raw.decode("ascii", errors="ignore").strip("\r\n\x02\x03 \t")
        except Exception:  # pragma: no cover
            continue
        if text:
            out.append(text)

    return out


# A weight token can show up as `1.234`, `01.234`, `+1.234`, ` 12345 ` (grams),
# possibly followed by `kg` / `g`. We grab the SIGN + DIGITS + optional decimal,
# and a separate flag tells us the unit.
_WEIGHT_RE = re.compile(
    r"(?P<sign>[+\-]?)\s*(?P<int>\d{1,5})(?:[.,](?P<frac>\d{1,4}))?\s*(?P<unit>kg|g)?",
    re.IGNORECASE,
)


def parse_weight_line(
    line: str, *, default_unit: str = "kg"
) -> tuple[Decimal, str] | None:
    """Pull the first weight token out of a line. Returns (kg, unit) or None.

    The unit returned is what the scale REPORTED ("kg" or "g") — useful for
    debug logs. The Decimal returned is ALWAYS in kg.

    We scan ALL matches and prefer (in order):
      1. A token followed by an explicit unit ("1.234kg", "12345g")
      2. A token with a decimal point ("1.234")
      3. Any other numeric token (last resort).
    This keeps frames like ``01,P:1.234,T:0.000,N:1.234`` from being parsed as
    "01" — that leading id has neither a unit nor a decimal.
    """
    candidates: list[tuple[int, Decimal, str, bool, bool]] = []
    # idx, value, unit_text, has_unit, has_frac
    for idx, match in enumerate(_WEIGHT_RE.finditer(line)):
        sign = match.group("sign") or ""
        int_part = match.group("int")
        frac_part = match.group("frac") or ""
        explicit_unit = match.group("unit")
        unit_text = (explicit_unit or default_unit).lower()

        raw = f"{sign}{int_part}.{frac_part}" if frac_part else f"{sign}{int_part}"
        try:
            value = Decimal(raw)
        except InvalidOperation:
            continue
        has_unit = explicit_unit is not None
        has_frac = bool(frac_part)
        candidates.append((idx, value, unit_text, has_unit, has_frac))

    if not candidates:
        return None

    # Priority: with unit > with decimal > anything. Tie-break by source order.
    def rank(c: tuple[int, Decimal, str, bool, bool]) -> tuple[int, int]:
        _idx, _val, _u, has_unit, has_frac = c
        # Lower = better. Earlier index breaks ties.
        primary = 0 if has_unit else (1 if has_frac else 2)
        return (primary, c[0])

    candidates.sort(key=rank)
    _, value, unit_text, has_unit, has_frac = candidates[0]

    # Many Argentine scales transmit grams as a 5-digit integer (e.g. "12345"
    # = 12.345 kg). If the chosen token has no unit AND no decimal AND the
    # integer part is >= 4 digits, assume grams.
    if not has_unit and not has_frac:
        digits = sum(ch.isdigit() for ch in str(value))
        if digits >= 4:
            unit_text = "g"

    if unit_text == "g":
        kg = (value / Decimal(1000)).quantize(Decimal("0.001"))
    else:
        kg = value.quantize(Decimal("0.001"))

    return kg, unit_text


def is_stable_marker(line: str) -> bool:
    """Heuristic: most retail scale frames embed an `ST` (stable) or `US`
    (unstable / motion) marker. Markers may appear surrounded by spaces,
    commas, or as a token at the start/end of the line. Default to True when
    no marker shows up — many scales only emit a frame after the load has
    settled.
    """
    upper = line.upper()
    # Tokenize on common separators (space, comma, semicolon).
    tokens = {t for t in re.split(r"[\s,;]+", upper) if t}
    if "US" in tokens or "MOTION" in tokens or "UNSTABLE" in tokens:
        return False
    if "ST" in tokens or "STABLE" in tokens:
        return True
    return True
