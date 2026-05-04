"""Schemas para Familia, Rubro, Subrubro y Marca."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _FamiliaFields(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=100)
    orden: int = 0


class FamiliaCreate(_FamiliaFields):
    pass


class FamiliaUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=20)
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    orden: int | None = None


class FamiliaOut(_FamiliaFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime


class _RubroFields(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=100)
    orden: int = 0


class RubroCreate(_RubroFields):
    pass


class RubroUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=20)
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    orden: int | None = None


class RubroOut(_RubroFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    familia_id: int
    created_at: datetime


class _SubrubroFields(BaseModel):
    codigo: str = Field(min_length=1, max_length=20)
    nombre: str = Field(min_length=1, max_length=100)
    orden: int = 0


class SubrubroCreate(_SubrubroFields):
    pass


class SubrubroUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=20)
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    orden: int | None = None


class SubrubroOut(_SubrubroFields):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rubro_id: int
    created_at: datetime


class MarcaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    activa: bool = True


class MarcaUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=100)
    activa: bool | None = None


class MarcaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    activa: bool
    created_at: datetime
