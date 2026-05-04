"""Application settings — loaded from .env / environment variables."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _hex_or_int(v: str | int) -> int:
    """Parse "0x0fe6" or "4070" as int."""
    if isinstance(v, int):
        return v
    s = str(v).strip()
    return int(s, 16) if s.lower().startswith("0x") else int(s)


class Settings(BaseSettings):
    """Runtime settings for the Jarvis POS Agent.

    Values are loaded from environment variables and `.env` (in working dir).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # HTTP server
    JARVIS_AGENT_HOST: str = "127.0.0.1"
    JARVIS_AGENT_PORT: int = 9123

    # Printer mode
    PRINTER_MODE: Literal["mock", "usb", "network"] = "mock"

    # USB (3NSTAR PRP-080 default IDs)
    PRINTER_USB_VENDOR: int = Field(default=0x0FE6)
    PRINTER_USB_PRODUCT: int = Field(default=0x811E)
    PRINTER_USB_INTERFACE: int = 0
    PRINTER_USB_IN_EP: int = Field(default=0x82)
    PRINTER_USB_OUT_EP: int = Field(default=0x02)

    # Network (3NSTAR Ethernet)
    PRINTER_NETWORK_HOST: str = "192.168.1.50"
    PRINTER_NETWORK_PORT: int = 9100

    # Paper config
    PRINTER_PAPER_WIDTH_MM: int = 80

    # Scale (balanza) — Kretz / Systel / Network / Mock
    SCALE_MODE: Literal["mock", "kretz", "systel", "network"] = "mock"
    SCALE_PORT: str = "COM3"  # Windows; "/dev/ttyUSB0" en Linux
    SCALE_BAUDRATE: int = 9600
    SCALE_HOST: str = "192.168.1.60"  # SCALE_MODE=network
    SCALE_NETWORK_PORT: int = 1001
    SCALE_TIMEOUT_SEC: float = 1.0

    # Output dir
    OUTPUT_DIR: str = "output"

    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:1420"

    @field_validator(
        "PRINTER_USB_VENDOR",
        "PRINTER_USB_PRODUCT",
        "PRINTER_USB_IN_EP",
        "PRINTER_USB_OUT_EP",
        mode="before",
    )
    @classmethod
    def _coerce_hex(cls, v: object) -> int:
        return _hex_or_int(v)  # type: ignore[arg-type]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def output_dir_path(self) -> Path:
        p = Path(self.OUTPUT_DIR)
        if not p.is_absolute():
            p = Path.cwd() / p
        p.mkdir(parents=True, exist_ok=True)
        return p


_settings: Settings | None = None


def get_settings() -> Settings:
    """Return cached Settings singleton."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


def reset_settings_cache() -> None:
    """For tests."""
    global _settings
    _settings = None
