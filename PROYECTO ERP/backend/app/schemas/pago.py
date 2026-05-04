"""Schemas Pydantic para FacturaPago."""
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.pago import MedioPagoEnum


class FacturaPagoCreate(BaseModel):
    medio: MedioPagoEnum
    monto: Decimal = Field(gt=0)
    referencia: str | None = Field(default=None, max_length=100)


class FacturaPagoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    medio: MedioPagoEnum
    monto: Decimal
    referencia: str | None
    orden: int
