"""Modelo MovimientoCaja — el ledger universal de movimientos financieros.

Inspirado en RESUMEN.DBF del sistema viejo (ver `analysis/cashier-domain`). Cada
fila es un evento financiero inmutable. Desde acá se proyectan: saldo de caja,
saldo por cliente/proveedor, cartera de cheques, tesoro, etc.

En 2.1 sólo escribimos rows de tipo `venta` y `devolucion` (anulación) desde el
flujo POS. Los otros tipos quedan reservados para 2.3+.
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin
from .pago import MedioPagoEnum


class TipoMovimientoEnum(enum.StrEnum):
    venta = "venta"
    devolucion = "devolucion"
    cobranza = "cobranza"
    pago_proveedor = "pago_proveedor"
    apertura_caja = "apertura_caja"
    cierre_caja = "cierre_caja"
    ingreso_efectivo = "ingreso_efectivo"
    egreso_efectivo = "egreso_efectivo"
    ajuste = "ajuste"
    cheque_recibido = "cheque_recibido"
    cheque_entregado = "cheque_entregado"


class MovimientoCaja(Base, TimestampMixin):
    """Evento financiero atómico en la caja/ledger universal."""

    __tablename__ = "movimientos_caja"

    id: Mapped[int] = mapped_column(primary_key=True)
    sucursal_id: Mapped[int] = mapped_column(
        ForeignKey("sucursales.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    caja_numero: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    fecha_caja: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    tipo: Mapped[TipoMovimientoEnum] = mapped_column(
        Enum(TipoMovimientoEnum, name="tipo_movimiento_enum"),
        nullable=False,
        index=True,
    )
    medio: Mapped[MedioPagoEnum | None] = mapped_column(
        Enum(MedioPagoEnum, name="medio_pago_enum"),
        nullable=True,
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)

    factura_id: Mapped[int | None] = mapped_column(
        ForeignKey("facturas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    proveedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True, index=True
    )

    descripcion: Mapped[str] = mapped_column(String(200), nullable=False, default="")

    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    sucursal = relationship("Sucursal")
    factura = relationship("Factura")
    cliente = relationship("Cliente")
    proveedor = relationship("Proveedor")
    user = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<MovCaja {self.tipo.value} suc={self.sucursal_id} "
            f"${self.monto} fecha={self.fecha_caja}>"
        )
