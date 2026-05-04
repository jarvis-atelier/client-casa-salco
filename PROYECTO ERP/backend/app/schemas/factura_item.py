"""Schemas Pydantic para FacturaItem."""
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class FacturaItemCreate(BaseModel):
    """Payload mínimo que envía el cliente al crear una factura."""

    articulo_id: int
    cantidad: Decimal = Field(gt=0)
    precio_unitario: Decimal = Field(ge=0)
    descuento_porc: Decimal = Field(default=Decimal("0"), ge=0, le=100)


class FacturaItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    articulo_id: int
    codigo: str
    descripcion: str
    cantidad: Decimal
    precio_unitario: Decimal
    descuento_porc: Decimal
    iva_porc: Decimal
    iva_monto: Decimal
    subtotal: Decimal
    total: Decimal
    orden: int
