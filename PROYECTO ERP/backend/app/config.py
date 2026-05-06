"""Configuración del backend — cargada desde variables de entorno."""
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# Raiz del backend (donde esta pyproject.toml / wsgi.py)
BACKEND_ROOT = Path(__file__).resolve().parent.parent
INSTANCE_DIR = BACKEND_ROOT / "instance"
INSTANCE_DIR.mkdir(exist_ok=True)
AFIP_CERT_DIR_DEFAULT = INSTANCE_DIR / "afip_certs"
_DEFAULT_SQLITE_URL = f"sqlite:///{(INSTANCE_DIR / 'casasalco.db').as_posix()}"


class Settings(BaseSettings):
    """Configuración tipada vía Pydantic."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "Jarvis Core"
    FLASK_ENV: str = "development"
    FLASK_DEBUG: bool = True
    SECRET_KEY: str = "dev-secret-change-me"

    # Default dev: SQLite local (sin Docker). En prod .env sobrescribe con Postgres.
    DATABASE_URL: str = _DEFAULT_SQLITE_URL
    REDIS_URL: str | None = None

    JWT_SECRET_KEY: str = "dev-jwt-secret-change-me"
    JWT_ACCESS_TOKEN_EXPIRES: int = 3600
    JWT_REFRESH_TOKEN_EXPIRES: int = 2_592_000

    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    # AFIP / ARCA — Fase 2.2
    # AFIP_MODE: mock (dev), pyafipws (prod), disabled (test/CI sin AFIP)
    AFIP_MODE: Literal["mock", "pyafipws", "disabled"] = "mock"
    AFIP_HOMO: bool = True  # True = homologacion (testing), False = produccion
    AFIP_CUIT: str = "20000000001"  # CUIT del emisor (dev placeholder)
    AFIP_CERT_PATH: str | None = None  # ruta al certificado .crt
    AFIP_KEY_PATH: str | None = None   # ruta a la clave privada .key
    AFIP_CERT_DIR: str = str(AFIP_CERT_DIR_DEFAULT)  # donde guardamos certs por CUIT

    # OCR (lectura de comprobantes con Vision IA) — Fase 3
    # OCR_MODE: mock (dev sin key), anthropic (Claude Vision), gemini (Google Gemini Vision)
    OCR_MODE: Literal["mock", "anthropic", "gemini"] = "mock"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    GEMINI_API_KEY: str | None = None
    GEMINI_MODEL: str = "gemini-1.5-flash"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def jwt_access_timedelta(self) -> timedelta:
        return timedelta(seconds=self.JWT_ACCESS_TOKEN_EXPIRES)

    @property
    def jwt_refresh_timedelta(self) -> timedelta:
        return timedelta(seconds=self.JWT_REFRESH_TOKEN_EXPIRES)


@lru_cache
def get_settings() -> Settings:
    return Settings()
