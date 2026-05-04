"""Schemas Pydantic para Cliente."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.cliente import CondicionIvaEnum


class ClienteBase(BaseModel):
    codigo: str = Field(min_length=1, max_length=30)
    razon_social: str = Field(min_length=1, max_length=255)
    cuit: str | None = Field(default=None, max_length=15)
    condicion_iva: CondicionIvaEnum = CondicionIvaEnum.consumidor_final
    condicion_iva_receptor_id: int | None = None
    telefono: str | None = None
    email: EmailStr | None = None
    direccion: str | None = None
    cuenta_corriente: bool = False
    limite_cuenta_corriente: Decimal = Decimal("0")
    saldo: Decimal = Decimal("0")
    activo: bool = True


class ClienteCreate(ClienteBase):
    pass


class ClienteUpdate(BaseModel):
    codigo: str | None = Field(default=None, min_length=1, max_length=30)
    razon_social: str | None = Field(default=None, min_length=1, max_length=255)
    cuit: str | None = Field(default=None, max_length=15)
    condicion_iva: CondicionIvaEnum | None = None
    condicion_iva_receptor_id: int | None = None
    telefono: str | None = None
    email: EmailStr | None = None
    direccion: str | None = None
    cuenta_corriente: bool | None = None
    limite_cuenta_corriente: Decimal | None = None
    saldo: Decimal | None = None
    activo: bool | None = None


class ClienteOut(ClienteBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
