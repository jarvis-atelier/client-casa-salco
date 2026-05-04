"""Mock scale — generates plausible weight readings without any hardware.

Each call to `get_weight()` walks the previous weight by a small random delta
(so the UI shows a *moving* number rather than constants), clamped to a sane
range. 80% of samples come back `stable=True`, 20% `stable=False` — that lets
the frontend exercise its "esperá un momento" warning without needing a real
scale that's mid-settling.

Intended for development and demos only. The factory falls back to this driver
when no real scale is configured (or when the real driver fails to import).
"""
from __future__ import annotations

import logging
import random
from datetime import datetime
from decimal import Decimal

from .base import IScaleDriver, ScaleStatus, WeightReading

log = logging.getLogger(__name__)


class MockScale(IScaleDriver):
    """In-process scale that fakes a slowly-drifting weight reading."""

    name = "mock"

    # Bounds for the simulated platter (kg).
    _MIN_KG = Decimal("0.050")
    _MAX_KG = Decimal("5.000")

    def __init__(self, *, seed: int | None = None) -> None:
        self._rng = random.Random(seed)
        # Start somewhere believable so the very first reading already looks
        # like a deli counter measurement, not 0.
        self._current_kg: Decimal = self._round_kg(
            Decimal("0.250") + Decimal(str(self._rng.uniform(0, 1.5)))
        )
        self._tare_kg: Decimal = Decimal("0.000")
        self._last_reading: WeightReading | None = None

    # ------------------------------------------------------------------
    @staticmethod
    def _round_kg(value: Decimal) -> Decimal:
        """Quantize to grams (3 decimals)."""
        return value.quantize(Decimal("0.001"))

    # ------------------------------------------------------------------
    def get_weight(self) -> WeightReading:
        # Drift up to ±20 g between calls so the UI sees motion.
        delta = Decimal(str(self._rng.uniform(-0.020, 0.020)))
        nxt = self._current_kg + delta
        if nxt < self._MIN_KG:
            nxt = self._MIN_KG + Decimal("0.010")
        elif nxt > self._MAX_KG:
            nxt = self._MAX_KG - Decimal("0.010")
        self._current_kg = self._round_kg(nxt)

        stable = self._rng.random() >= 0.20  # ~80% stable
        reading = WeightReading(
            weight_kg=self._current_kg,
            stable=stable,
            tare_kg=self._tare_kg,
            unit="kg",
            timestamp=datetime.now(),
            raw_response=f"MOCK,{self._current_kg},{'ST' if stable else 'US'}",
        )
        self._last_reading = reading
        return reading

    # ------------------------------------------------------------------
    def tare(self) -> bool:
        # Tare = treat the current load as the new zero.
        self._tare_kg = self._current_kg
        self._current_kg = self._round_kg(Decimal("0.000"))
        log.info("mock scale tared (tare=%s kg)", self._tare_kg)
        return True

    # ------------------------------------------------------------------
    def status(self) -> ScaleStatus:
        return ScaleStatus(
            status="ready",
            driver="mock",
            model="mock-scale",
            online=True,
            port=None,
            last_weight_kg=(
                self._last_reading.weight_kg if self._last_reading else None
            ),
            detail="modo mock — peso simulado",
        )

    # ------------------------------------------------------------------
    def close(self) -> None:
        # Nothing to release.
        return None
