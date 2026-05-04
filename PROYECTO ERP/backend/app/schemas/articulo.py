"""Schemas Pydantic para Articulo."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.articulo import UnidadMedidaEnum


class ArticuloBase(BaseModel):
    codigo: str = Field(min_length=1, max_length=30)
    codigo_barras: str | None = Field(default=None, max_length=50)
    descripcion: str = Field(min_length=1, max_length=255)
    descripcion_corta: str | None = Field(default=None, max_length=100)
    familia_id: int | None = None
    rubro_id: int | None = None
    subrubro_id: int | None = None
    marca_id: int | None = None
    proveedor_principal_id: int | None = None
    unidad_medida: UnidadMedidaEnum = UnidadMedidaEnum.unidad
    controla_stock: bool = True
    controla_vencimiento: bool = False
    costo: Decimal = Decimal("0")
    pvp_base: Decimal = Decimal("0")
    iva_porc: Decimal = Decimal("21")
    activo: bool = True


class ArticuloCreate(ArticuloBase):
    pass


class ArticuloUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=30)
    codigo_barras: str | None = Field(default=None, max_length=50)
    descripcion: str | None = Field(default=None, min_length=1, max_length=255)
    descripcion_corta: str | None = Field(default=None, max_length=100)
    familia_id: int | None = None
    rubro_id: int | None = None
    subrubro_id: int | None = None
    marca_id: int | None = None
    proveedor_principal_id: int | None = None
    unidad_medida: UnidadMedidaEnum | None = None
    controla_stock: bool | None = None
    controla_vencimiento: bool | None = None
    costo: Decimal | None = None
    pvp_base: Decimal | None = None
    iva_porc: Decimal | None = None
    activo: bool | None = None


class ArticuloOut(ArticuloBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
