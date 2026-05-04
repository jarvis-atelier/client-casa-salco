"""Schemas Pydantic para ComercioConfig (singleton)."""
from __future__ import annotations

import re
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

CUIT_PATTERN = re.compile(r"^\d{2}-?\d{8}-?\d{1}$")


def _validate_cuit_optional(value: str | None) -> str | None:
    if value is None:
        return value
    v = value.strip()
    if v == "":
        return ""
    if not CUIT_PATTERN.match(v):
        raise ValueError("formato de CUIT inválido — usar XX-XXXXXXXX-X")
    return v


class ComercioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    razon_social: str
    nombre_fantasia: str | None
    cuit: str
    condicion_iva: str
    domicilio: str | None
    localidad: str | None
    provincia: str | None
    cp: str | None
    telefono: str | None
    email: str | None
    iibb: str | None
    inicio_actividades: date | None
    logo_path: str | None
    pie_ticket: str | None
    created_at: datetime
    updated_at: datetime


class ComercioUpdate(BaseModel):
    razon_social: str | None = Field(default=None, max_length=200)
    nombre_fantasia: str | None = Field(default=None, max_length=200)
    cuit: str | None = Field(default=None, max_length=13)
    condicion_iva: str | None = Field(default=None, max_length=40)
    domicilio: str | None = Field(default=None, max_length=200)
    localidad: str | None = Field(default=None, max_length=100)
    provincia: str | None = Field(default=None, max_length=100)
    cp: str | None = Field(default=None, max_length=10)
    telefono: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    iibb: str | None = Field(default=None, max_length=50)
    inicio_actividades: date | None = None
    logo_path: str | None = Field(default=None, max_length=255)
    pie_ticket: str | None = Field(default=None, max_length=255)

    @field_validator("cuit")
    @classmethod
    def _check_cuit(cls, v: str | None) -> str | None:
        return _validate_cuit_optional(v)
