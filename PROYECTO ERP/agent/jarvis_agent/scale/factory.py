"""Scale driver selector — picks the concrete driver based on settings.

The agent caches a single driver instance per process (singleton). Opening a
COM port or TCP socket on every request would be too slow for the POS UX, and
serial ports usually can't be opened twice anyway.

If the requested real driver fails to import or instantiate (missing
`pyserial`, no such COM port, etc), we log a loud warning and fall back to
the mock driver so the rest of the agent keeps running.
"""
from __future__ import annotations

import logging
from threading import Lock

from ..config import Settings, get_settings
from .base import IScaleDriver

log = logging.getLogger(__name__)

_instance: IScaleDriver | None = None
_lock = Lock()


def _build(settings: Settings) -> IScaleDriver:
    mode = settings.SCALE_MODE

    if mode == "mock":
        from .mock import MockScale

        return MockScale()

    if mode == "kretz":
        try:
            from .kretz import KretzScale

            return KretzScale(
                port=settings.SCALE_PORT,
                baudrate=settings.SCALE_BAUDRATE,
                timeout=settings.SCALE_TIMEOUT_SEC,
            )
        except Exception as exc:  # pragma: no cover - depends on hardware
            log.warning("Kretz driver unavailable (%s) — falling back to mock", exc)
            from .mock import MockScale

            return MockScale()

    if mode == "systel":
        try:
            from .systel import SystelScale

            return SystelScale(
                port=settings.SCALE_PORT,
                baudrate=settings.SCALE_BAUDRATE,
                timeout=settings.SCALE_TIMEOUT_SEC,
            )
        except Exception as exc:  # pragma: no cover - depends on hardware
            log.warning("Systel driver unavailable (%s) — falling back to mock", exc)
            from .mock import MockScale

            return MockScale()

    if mode == "network":
        try:
            from .network import NetworkScale

            return NetworkScale(
                host=settings.SCALE_HOST,
                port=settings.SCALE_NETWORK_PORT,
                timeout=settings.SCALE_TIMEOUT_SEC,
            )
        except Exception as exc:  # pragma: no cover - depends on network
            log.warning("Network scale unavailable (%s) — falling back to mock", exc)
            from .mock import MockScale

            return MockScale()

    raise ValueError(f"SCALE_MODE invalido: {mode}")


def get_scale(settings: Settings | None = None) -> IScaleDriver:
    """Return the cached `IScaleDriver` (mock | kretz | systel | network)."""
    global _instance
    settings = settings or get_settings()
    with _lock:
        if _instance is None:
            _instance = _build(settings)
        return _instance


def reset_scale_cache() -> None:
    """For tests + hot-reload. Closes the current driver if any."""
    global _instance
    with _lock:
        if _instance is not None:
            try:
                _instance.close()
            except Exception:  # pragma: no cover
                pass
        _instance = None
