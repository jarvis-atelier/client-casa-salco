"""Scale drivers — Kretz / Systel / Network / Mock.

Bridges the web POS to electronic scales (Kretz, Systel) commonly used in
Argentine grocery counters. Drivers expose a uniform `IScaleDriver` interface
so the API layer doesn't care whether the weight comes from a serial COM port,
an Ethernet TCP socket, or the in-process mock.
"""
from .base import IScaleDriver, ScaleError, ScaleStatus, WeightReading  # noqa: F401
