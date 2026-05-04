"""Schemas Pydantic para Sucursal y Area."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SucursalBase(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=200)
    direccion: str | None = None
    ciudad: str | None = None
    provincia: str | None = None
    lat: Decimal | None = None
    lng: Decimal | None = None
    telefono: str | None = None
    activa: bool = True


class SucursalCreate(SucursalBase):
    pass


class SucursalUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=20)
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    direccion: str | None = None
    ciudad: str | None = None
    provincia: str | None = None
    lat: Decimal | None = None
    lng: Decimal | None = None
    telefono: str | None = None
    activa: bool | None = None


class SucursalOut(SucursalBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class AreaBase(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    codigo: str = Field(min_length=1, max_length=20)
    descripcion: str | None = None
    activa: bool = True
    orden: int = 0


class AreaCreate(AreaBase):
    pass


class AreaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    codigo: str | None = Field(default=None, min_length=1, max_length=20)
    descripcion: str | None = None
    activa: bool | None = None
    orden: int | None = None


class AreaOut(AreaBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sucursal_id: int
    created_at: datetime
    updated_at: datetime
