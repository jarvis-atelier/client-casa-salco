"""Tests for the scale subsystem.

Real hardware drivers (Kretz / Systel / Network) require a physical scale
plugged into a COM port or reachable over TCP, so they're skipped unless
`SCALE_HARDWARE=1` is exported in the environment. The mock driver — used in
production-dev to exercise the POS UX without hardware — is fully covered.
"""
from __future__ import annotations

import os
from decimal import Decimal

import pytest

from jarvis_agent.config import Settings, reset_settings_cache
from jarvis_agent.scale.factory import get_scale, reset_scale_cache
from jarvis_agent.scale.mock import MockScale
from jarvis_agent.scale._serial_common import (
    is_stable_marker,
    parse_weight_line,
)


# ---------------------------------------------------------------------------
# MockScale unit tests
# ---------------------------------------------------------------------------


class TestMockScale:
    def test_get_weight_returns_kg_in_range(self):
        scale = MockScale(seed=1)
        r = scale.get_weight()
        assert r.unit == "kg"
        assert isinstance(r.weight_kg, Decimal)
        assert Decimal("0.040") <= r.weight_kg <= Decimal("5.010")
        assert r.timestamp is not None

    def test_weight_drifts_between_calls(self):
        # Different RNG draws should give different but plausible readings.
        scale = MockScale(seed=1)
        readings = [scale.get_weight().weight_kg for _ in range(5)]
        assert len(set(readings)) > 1, "mock scale should drift, got constant"

    def test_stability_distribution(self):
        scale = MockScale(seed=7)
        flags = [scale.get_weight().stable for _ in range(200)]
        true_ratio = sum(flags) / len(flags)
        # ~80% stable; allow ±15% slack for sample size.
        assert 0.65 <= true_ratio <= 0.95

    def test_tare_returns_true_and_zeros_platter(self):
        scale = MockScale(seed=3)
        scale.get_weight()  # establish a reading
        ok = scale.tare()
        assert ok is True
        # After taring the next reading should start near zero (drift up to
        # a few grams via the random walk).
        r = scale.get_weight()
        assert r.tare_kg > Decimal("0.000")
        assert r.weight_kg < Decimal("0.100")

    def test_status_reports_ready_mock(self):
        scale = MockScale(seed=5)
        s = scale.status()
        assert s.driver == "mock"
        assert s.online is True
        assert s.status == "ready"

    def test_close_is_idempotent(self):
        scale = MockScale(seed=9)
        scale.close()
        scale.close()  # must not raise


# ---------------------------------------------------------------------------
# Serial parser unit tests (no hardware required — tests pure helpers)
# ---------------------------------------------------------------------------


class TestSerialParser:
    @pytest.mark.parametrize(
        "line, expected_kg",
        [
            ("ST,GS,+0001.234kg", Decimal("1.234")),
            ("01,P:1.234,T:0.000,N:1.234", Decimal("1.234")),
            ("+ 1.234 kg ST", Decimal("1.234")),
            ("+1.234kg", Decimal("1.234")),
            (" 12345 ", Decimal("12.345")),  # 5-digit grams, no unit
            ("US 0.500 kg", Decimal("0.500")),
            ("+12345g", Decimal("12.345")),
        ],
    )
    def test_parses_common_frames(self, line: str, expected_kg: Decimal):
        parsed = parse_weight_line(line)
        assert parsed is not None, f"failed to parse {line!r}"
        kg, _unit = parsed
        assert kg == expected_kg

    def test_rejects_non_weight_line(self):
        assert parse_weight_line("ERROR") is None
        assert parse_weight_line("") is None

    def test_stable_marker_detection(self):
        assert is_stable_marker("ST,GS,+0001.234kg") is True
        assert is_stable_marker("US,GS,+0001.234kg") is False
        assert is_stable_marker("STABLE 1.234") is True
        assert is_stable_marker("MOTION 1.234") is False
        # Default true when no marker.
        assert is_stable_marker("+1.234 kg") is True


# ---------------------------------------------------------------------------
# Factory tests
# ---------------------------------------------------------------------------


class TestFactory:
    def setup_method(self):
        reset_settings_cache()
        reset_scale_cache()

    def teardown_method(self):
        reset_settings_cache()
        reset_scale_cache()

    def test_factory_returns_mock_when_mode_is_mock(self):
        s = Settings(SCALE_MODE="mock")
        driver = get_scale(s)
        assert driver.name == "mock"
        assert isinstance(driver, MockScale)

    def test_factory_caches_singleton(self):
        s = Settings(SCALE_MODE="mock")
        a = get_scale(s)
        b = get_scale(s)
        assert a is b

    def test_factory_reset_drops_singleton(self):
        s = Settings(SCALE_MODE="mock")
        a = get_scale(s)
        reset_scale_cache()
        b = get_scale(s)
        assert a is not b


# ---------------------------------------------------------------------------
# HTTP integration tests (uses fixture in conftest with a seeded MockScale)
# ---------------------------------------------------------------------------


class TestScaleApi:
    def test_status_endpoint_returns_mock(self, client):
        r = client.get("/scale/status")
        assert r.status_code == 200
        body = r.get_json()
        assert body["driver"] == "mock"
        assert body["online"] is True
        assert body["status"] == "ready"

    def test_weight_endpoint_returns_decimal(self, client):
        r = client.get("/scale/weight")
        assert r.status_code == 200, r.get_json()
        body = r.get_json()
        assert body["ok"] is True
        assert body["driver"] == "mock"
        assert body["unit"] == "kg"
        kg = Decimal(body["weight_kg"])
        assert kg > Decimal("0")
        assert isinstance(body["stable"], bool)
        assert "timestamp" in body

    def test_weight_endpoint_changes_between_calls(self, client):
        a = Decimal(client.get("/scale/weight").get_json()["weight_kg"])
        # Burn a few samples — mock drifts ~10 g per call.
        for _ in range(3):
            client.get("/scale/weight")
        b = Decimal(client.get("/scale/weight").get_json()["weight_kg"])
        # Almost guaranteed to differ across 4 draws.
        assert a != b

    def test_tare_endpoint_returns_ok(self, client):
        r = client.post("/scale/tare")
        assert r.status_code == 200
        body = r.get_json()
        assert body["ok"] is True
        assert body["driver"] == "mock"

    def test_status_after_weight_includes_last_reading(self, client):
        client.get("/scale/weight")
        body = client.get("/scale/status").get_json()
        assert body["last_weight_kg"] is not None


# ---------------------------------------------------------------------------
# Real-hardware tests — opt-in via SCALE_HARDWARE=1
# ---------------------------------------------------------------------------


pytestmark_hw = pytest.mark.skipif(
    not os.getenv("SCALE_HARDWARE"),
    reason="requires real Kretz/Systel scale (set SCALE_HARDWARE=1 to run)",
)


@pytestmark_hw
class TestRealHardware:  # pragma: no cover
    def test_kretz_reads_weight(self):
        from jarvis_agent.scale.kretz import KretzScale

        port = os.environ.get("SCALE_PORT", "COM3")
        scale = KretzScale(port=port)
        r = scale.get_weight()
        assert r.weight_kg >= Decimal("0")
        scale.close()

    def test_systel_reads_weight(self):
        from jarvis_agent.scale.systel import SystelScale

        port = os.environ.get("SCALE_PORT", "COM3")
        scale = SystelScale(port=port)
        r = scale.get_weight()
        assert r.weight_kg >= Decimal("0")
        scale.close()
