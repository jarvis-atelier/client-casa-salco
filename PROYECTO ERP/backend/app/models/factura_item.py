"""Modelo FacturaItem — líneas/renglones de una factura."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base

if TYPE_CHECKING:
    from .factura import Factura


class FacturaItem(Base):
    """Renglón de una factura. Se congelan código y descripción al momento de emitir.

    Subtotal (sin IVA) = cantidad * precio_unitario - descuento_porc_aplicado
    Total (con IVA)    = subtotal + iva_monto
    """

    __tablename__ = "factura_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    factura_id: Mapped[int] = mapped_column(
        ForeignKey("facturas.id", ondelete="CASCADE"), nullable=False, index=True
    )
    articulo_id: Mapped[int] = mapped_column(
        ForeignKey("articulos.id", ondelete="RESTRICT"), nullable=False, index=True
    )

    codigo: Mapped[str] = mapped_column(String(30), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False)
    cantidad: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    precio_unitario: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    descuento_porc: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=0
    )
    iva_porc: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    iva_monto: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    total: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    factura: Mapped[Factura] = relationship("Factura", back_populates="items")
    articulo = relationship("Articulo")

    def __repr__(self) -> str:
        return f"<FacturaItem factura={self.factura_id} art={self.articulo_id} qty={self.cantidad}>"
