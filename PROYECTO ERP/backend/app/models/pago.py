"""Modelo FacturaPago — medios de pago aplicados a un comprobante (split payments)."""
from __future__ import annotations

import enum
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .factura import Factura


class MedioPagoEnum(enum.StrEnum):
    efectivo = "efectivo"
    tarjeta_debito = "tarjeta_debito"
    tarjeta_credito = "tarjeta_credito"
    transferencia = "transferencia"
    qr_mercadopago = "qr_mercadopago"
    qr_modo = "qr_modo"
    cheque = "cheque"
    cuenta_corriente = "cuenta_corriente"
    vale = "vale"


class FacturaPago(Base):
    """Un medio de pago aplicado a una factura. Permite split (efectivo + tarjeta)."""

    __tablename__ = "factura_pagos"

    id: Mapped[int] = mapped_column(primary_key=True)
    factura_id: Mapped[int] = mapped_column(
        ForeignKey("facturas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    medio: Mapped[MedioPagoEnum] = mapped_column(
        Enum(MedioPagoEnum, name="medio_pago_enum"),
        nullable=False,
    )
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    referencia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    factura: Mapped[Factura] = relationship("Factura", back_populates="pagos")

    def __repr__(self) -> str:
        return f"<FacturaPago factura={self.factura_id} {self.medio.value} ${self.monto}>"
