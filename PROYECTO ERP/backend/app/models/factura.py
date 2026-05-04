"""Modelo Factura — comprobantes de venta (ticket, factura A/B/C, NC, remito, presupuesto)."""
from __future__ import annotations

import enum
from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .factura_item import FacturaItem
    from .pago import FacturaPago


class TipoComprobanteEnum(enum.StrEnum):
    factura_a = "factura_a"
    factura_b = "factura_b"
    factura_c = "factura_c"
    ticket = "ticket"
    nota_credito_a = "nc_a"
    nota_credito_b = "nc_b"
    nota_credito_c = "nc_c"
    remito = "remito"
    presupuesto = "presupuesto"


class EstadoComprobanteEnum(enum.StrEnum):
    borrador = "borrador"
    emitida = "emitida"
    anulada = "anulada"


class Factura(Base, TimestampMixin):
    """Factura (comprobante) — cabecera de una venta.

    La numeración es secuencial por (sucursal, punto_venta, tipo). Los campos
    de CAE/AFIP se rellenan en Fase 2.2 por el servicio fiscal — en 2.1 quedan
    en null (tipo ticket no requiere CAE siempre; A/B/C sí lo requerirán).
    """

    __tablename__ = "facturas"
    __table_args__ = (
        UniqueConstraint(
            "sucursal_id",
            "punto_venta",
            "tipo",
            "numero",
            name="uq_facturas_suc_pv_tipo_nro",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sucursal_id: Mapped[int] = mapped_column(
        ForeignKey("sucursales.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    punto_venta: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    tipo: Mapped[TipoComprobanteEnum] = mapped_column(
        Enum(TipoComprobanteEnum, name="tipo_comprobante_enum"),
        nullable=False,
        index=True,
    )
    numero: Mapped[int] = mapped_column(Integer, nullable=False)
    fecha: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    cliente_id: Mapped[int | None] = mapped_column(
        ForeignKey("clientes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    cajero_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    estado: Mapped[EstadoComprobanteEnum] = mapped_column(
        Enum(EstadoComprobanteEnum, name="estado_comprobante_enum"),
        nullable=False,
        default=EstadoComprobanteEnum.borrador,
        index=True,
    )

    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_iva: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    total_descuento: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    moneda: Mapped[str] = mapped_column(String(5), nullable=False, default="ARS")
    cotizacion: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=1)

    observacion: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Campos AFIP — los llena Fase 2.2.
    cae: Mapped[str | None] = mapped_column(String(32), nullable=True)
    cae_vencimiento: Mapped[date | None] = mapped_column(Date, nullable=True)
    qr_afip: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Anulación
    anulada_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    anulada_por_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Para notas de crédito: referencia a la factura origen.
    factura_origen_id: Mapped[int | None] = mapped_column(
        ForeignKey("facturas.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Espacio para campos futuros sin migración.
    legacy_meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Relaciones
    sucursal = relationship("Sucursal")
    cliente = relationship("Cliente")
    cajero = relationship("User", foreign_keys=[cajero_id])
    anulada_por = relationship("User", foreign_keys=[anulada_por_user_id])
    factura_origen = relationship("Factura", remote_side="Factura.id")

    items: Mapped[list[FacturaItem]] = relationship(
        "FacturaItem",
        back_populates="factura",
        cascade="all, delete-orphan",
        order_by="FacturaItem.orden",
    )
    pagos: Mapped[list[FacturaPago]] = relationship(
        "FacturaPago",
        back_populates="factura",
        cascade="all, delete-orphan",
        order_by="FacturaPago.orden",
    )

    def __repr__(self) -> str:
        return (
            f"<Factura {self.tipo.value} "
            f"{self.punto_venta:04d}-{self.numero:08d} suc={self.sucursal_id}>"
        )
