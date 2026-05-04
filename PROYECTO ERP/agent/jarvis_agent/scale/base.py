"""Abstract scale driver interface + reading / error / status types.

The agent picks one concrete driver at startup based on `SCALE_MODE`. Real
hardware drivers (Kretz, Systel) talk to the scale over a serial COM port; the
network driver speaks TCP/IP to scales with an Ethernet card; the mock driver
fakes a believable weight stream so the POS UI flow can be exercised without
any physical scale connected.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal


class ScaleError(Exception):
    """Raised when the physical scale (or the link to it) misbehaves.

    Mapped to HTTP 502 by the API layer with the message in the body.
    """

    def __init__(self, message: str, *, code: str = "scale_error") -> None:
        super().__init__(message)
        self.code = code


@dataclass
class WeightReading:
    """A single weight sample from the scale.

    `weight_kg` is ALWAYS in kilograms — drivers must convert if the scale
    reports in grams. `stable` mirrors the scale's own stability flag (some
    scales raise a "motion" bit while the load is still settling).
    """

    weight_kg: Decimal
    stable: bool
    tare_kg: Decimal
    unit: Literal["kg", "g"]
    timestamp: datetime
    raw_response: str | None = None


ScaleDriverName = Literal["mock", "kretz", "systel", "network"]
ScaleStatusValue = Literal["ready", "error", "offline"]


@dataclass
class ScaleStatus:
    """Runtime status returned by `IScaleDriver.status()`."""

    status: ScaleStatusValue
    driver: ScaleDriverName
    model: str = "unknown"
    online: bool = True
    port: str | None = None
    last_weight_kg: Decimal | None = None
    detail: str | None = None
    error: str | None = None
    extra: dict[str, str] = field(default_factory=dict)


class IScaleDriver(ABC):
    """Abstract scale driver."""

    name: ScaleDriverName = "mock"

    @abstractmethod
    def get_weight(self) -> WeightReading:
        """Return the current weight on the platter.

        Raise `ScaleError` if the scale isn't reachable or returned garbage.
        """

    @abstractmethod
    def tare(self) -> bool:
        """Send a tare command (zero the platter). Return True on success."""

    @abstractmethod
    def status(self) -> ScaleStatus:
        """Return current driver/scale status — must NOT raise."""

    @abstractmethod
    def close(self) -> None:
        """Release the underlying resource (serial / socket). Idempotent."""
