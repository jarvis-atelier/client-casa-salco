"""Modelos del módulo Calendario de pagos.

Tres entidades:

- `CompromisoPago` — un vencimiento financiero a pagar (factura de compra,
  saldo de cuenta corriente, resumen de tarjeta, servicio, impuesto).
- `TarjetaCorporativa` — tarjeta de la empresa con días de cierre/vencimiento
  mensuales para auto-generar compromisos.
- `PagoCompromiso` — cada pago aplicado contra un compromiso (puede ser
  parcial: un compromiso puede tener varios pagos).

El módulo está pensado para que el detector `vencimiento_proximo` levante
alertas cuando un compromiso está cerca de su vencimiento o ya venció.
"""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class TipoCompromisoEnum(enum.StrEnum):
    factura_compra = "factura_compra"
    cuenta_corriente_proveedor = "cuenta_corriente_proveedor"
    tarjeta_corporativa = "tarjeta_corporativa"
    servicio = "servicio"
    impuesto = "impuesto"
    otro = "otro"


class EstadoCompromisoEnum(enum.StrEnum):
    pendiente = "pendiente"
    parcial = "parcial"
    pagado = "pagado"
    vencido = "vencido"
    cancelado = "cancelado"


class TarjetaCorporativa(Base, TimestampMixin):
    """Tarjeta de crédito corporativa con cierre y vencimiento mensual fijo."""

    __tablename__ = "tarjetas_corporativas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    banco: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ultimos_4: Mapped[str] = mapped_column(String(4), nullable=False)
    titular: Mapped[str | None] = mapped_column(String(150), nullable=True)
    limite_total: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 2), nullable=True
    )

    # Día del mes en que cierra el resumen (1..31).
    dia_cierre: Mapped[int] = mapped_column(Integer, nullable=False)
    # Día del mes en que vence el pago del resumen (1..31).
    dia_vencimiento: Mapped[int] = mapped_column(Integer, nullable=False)

    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<TarjetaCorporativa {self.nombre} ****{self.ultimos_4}>"


class CompromisoPago(Base, TimestampMixin):
    """Compromiso de pago — un vencimiento financiero pendiente."""

    __tablename__ = "compromisos_pago"

    id: Mapped[int] = mapped_column(primary_key=True)

    tipo: Mapped[TipoCompromisoEnum] = mapped_column(
        Enum(TipoCompromisoEnum, name="tipo_compromiso_enum"),
        nullable=False,
        index=True,
    )
    estado: Mapped[EstadoCompromisoEnum] = mapped_column(
        Enum(EstadoCompromisoEnum, name="estado_compromiso_enum"),
        nullable=False,
        default=EstadoCompromisoEnum.pendiente,
        index=True,
    )

    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    monto_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    monto_pagado: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )

    fecha_emision: Mapped[date | None] = mapped_column(Date, nullable=True)
    fecha_vencimiento: Mapped[date] = mapped_column(
        Date, nullable=False, index=True
    )
    fecha_pago_real: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Referencias opcionales (al menos una suele estar seteada según el tipo)
    proveedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True, index=True
    )
    factura_id: Mapped[int | None] = mapped_column(
        ForeignKey("facturas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tarjeta_id: Mapped[int | None] = mapped_column(
        ForeignKey("tarjetas_corporativas.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sucursal_id: Mapped[int | None] = mapped_column(
        ForeignKey("sucursales.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Audit
    creado_por_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    pagado_por_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    nota: Mapped[str | None] = mapped_column(Text, nullable=True)

    proveedor = relationship("Proveedor", foreign_keys=[proveedor_id])
    factura = relationship("Factura", foreign_keys=[factura_id])
    tarjeta = relationship("TarjetaCorporativa", foreign_keys=[tarjeta_id])
    sucursal = relationship("Sucursal", foreign_keys=[sucursal_id])
    creado_por = relationship("User", foreign_keys=[creado_por_user_id])
    pagado_por = relationship("User", foreign_keys=[pagado_por_user_id])

    pagos: Mapped[list[PagoCompromiso]] = relationship(
        "PagoCompromiso",
        back_populates="compromiso",
        cascade="all, delete-orphan",
        order_by="PagoCompromiso.fecha_pago",
    )

    @property
    def monto_pendiente(self) -> Decimal:
        total = self.monto_total or Decimal("0")
        pagado = self.monto_pagado or Decimal("0")
        return total - pagado

    @property
    def dias_para_vencer(self) -> int:
        if not self.fecha_vencimiento:
            return 0
        return (self.fecha_vencimiento - date.today()).days

    def __repr__(self) -> str:
        return (
            f"<CompromisoPago {self.tipo.value} ${self.monto_total} "
            f"vto={self.fecha_vencimiento} estado={self.estado.value}>"
        )


class PagoCompromiso(Base, TimestampMixin):
    """Pago aplicado contra un CompromisoPago. Soporta pagos parciales."""

    __tablename__ = "pagos_compromiso"

    id: Mapped[int] = mapped_column(primary_key=True)
    compromiso_id: Mapped[int] = mapped_column(
        ForeignKey("compromisos_pago.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    fecha_pago: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    monto: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    medio_pago: Mapped[str] = mapped_column(String(50), nullable=False)
    referencia: Mapped[str | None] = mapped_column(String(200), nullable=True)
    movimiento_caja_id: Mapped[int | None] = mapped_column(
        ForeignKey("movimientos_caja.id", ondelete="SET NULL"),
        nullable=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )

    compromiso = relationship("CompromisoPago", back_populates="pagos")
    movimiento_caja = relationship("MovimientoCaja", foreign_keys=[movimiento_caja_id])
    user = relationship("User", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return (
            f"<PagoCompromiso compromiso={self.compromiso_id} "
            f"${self.monto} {self.medio_pago} {self.fecha_pago}>"
        )


__all__ = [
    "CompromisoPago",
    "EstadoCompromisoEnum",
    "PagoCompromiso",
    "TarjetaCorporativa",
    "TipoCompromisoEnum",
]
