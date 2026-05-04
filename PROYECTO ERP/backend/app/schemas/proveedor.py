"""Schemas Pydantic para Proveedor."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class ProveedorBase(BaseModel):
    codigo: str = Field(min_length=1, max_length=30)
    razon_social: str = Field(min_length=1, max_length=255)
    cuit: str | None = Field(default=None, max_length=15)
    telefono: str | None = None
    email: EmailStr | None = None
    direccion: str | None = None
    activo: bool = True


class ProveedorCreate(ProveedorBase):
    pass


class ProveedorUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=30)
    razon_social: str | None = Field(default=None, min_length=1, max_length=255)
    cuit: str | None = Field(default=None, max_length=15)
    telefono: str | None = None
    email: EmailStr | None = None
    direccion: str | None = None
    activo: bool | None = None


class ProveedorOut(ProveedorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
