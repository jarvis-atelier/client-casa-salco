"""Schemas Pydantic para Factura."""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.factura import EstadoComprobanteEnum, TipoComprobanteEnum

from .factura_item import FacturaItemCreate, FacturaItemOut
from .pago import FacturaPagoCreate, FacturaPagoOut


class ClienteResumen(BaseModel):
    """Resumen de cliente embebido en respuestas de facturas para evitar N+1."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    razon_social: str
    cuit: str | None = None


class FacturaCreate(BaseModel):
    """Payload de creación de una factura completa (items + pagos en el mismo request).

    Reglas:
    - La suma de los `pagos.monto` debe igualar el total calculado (con tolerancia 0.01).
    - Cada item debe tener stock suficiente en la sucursal indicada.
    - El cliente, si se pasa, debe estar activo.
    """

    sucursal_id: int
    punto_venta: int = Field(default=1, ge=1, le=9999)
    tipo: TipoComprobanteEnum
    cliente_id: int | None = None
    observacion: str | None = None
    items: list[FacturaItemCreate] = Field(min_length=1)
    pagos: list[FacturaPagoCreate] = Field(min_length=1)


class FacturaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sucursal_id: int
    punto_venta: int
    tipo: TipoComprobanteEnum
    numero: int
    fecha: datetime

    cliente_id: int | None
    cajero_id: int
    estado: EstadoComprobanteEnum

    subtotal: Decimal
    total_iva: Decimal
    total_descuento: Decimal
    total: Decimal
    moneda: str
    cotizacion: Decimal

    observacion: str | None

    cae: str | None
    cae_vencimiento: date | None
    qr_afip: str | None

    anulada_at: datetime | None
    anulada_por_user_id: int | None
    factura_origen_id: int | None

    created_at: datetime
    updated_at: datetime

    items: list[FacturaItemOut] = []
    pagos: list[FacturaPagoOut] = []

    cliente_nombre: str | None = None
    cliente_resumen: ClienteResumen | None = None
