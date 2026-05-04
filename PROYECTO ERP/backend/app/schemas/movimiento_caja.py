"""Schemas Pydantic para MovimientoCaja (ledger)."""
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.pago import MedioPagoEnum
from app.models.resumen import TipoMovimientoEnum


class MovimientoCajaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sucursal_id: int
    caja_numero: int
    fecha_caja: date
    fecha: datetime
    tipo: TipoMovimientoEnum
    medio: MedioPagoEnum | None
    monto: Decimal
    factura_id: int | None
    cliente_id: int | None
    proveedor_id: int | None
    descripcion: str
    user_id: int | None
    created_at: datetime
    updated_at: datetime
