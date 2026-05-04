"""Modelo StockSucursal — stock por (articulo, sucursal).

Opción C — stock inteligente:
- `cantidad`: stock actual on-hand (ya existía).
- `stock_minimo`, `stock_maximo`, `punto_reorden`: umbrales por sucursal
  (override del default del Articulo). NULL → usar default.
- `lead_time_dias`: lead time del proveedor para esta sucursal (override).
- `stock_optimo_calculado`: calculado por velocidad de venta × lead time × factor.
- `ultima_recalculacion`: timestamp del último recálculo automático.
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class StockSucursal(Base, TimestampMixin):
    """Stock on-hand de un artículo en una sucursal puntual.

    Se crea en cero la primera vez que hace falta (ver `ensure_stock_row` en
    el servicio de stock). Las modificaciones deben pasar siempre por el
    servicio — nunca escribir directo desde una vista.
    """

    __tablename__ = "stock_sucursal"
    __table_args__ = (
        UniqueConstraint("articulo_id", "sucursal_id", name="uq_stock_art_suc"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    articulo_id: Mapped[int] = mapped_column(
        ForeignKey("articulos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sucursal_id: Mapped[int] = mapped_column(
        ForeignKey("sucursales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    cantidad: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)

    # Stock inteligente — opción C: override por sucursal.
    # Si están en NULL, se usa el default del articulo.
    stock_minimo: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    stock_maximo: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    punto_reorden: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    lead_time_dias: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Calculados por el job `actualizar_stock_optimo_y_reorden_auto`.
    stock_optimo_calculado: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    ultima_recalculacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    articulo = relationship("Articulo")
    sucursal = relationship("Sucursal")

    # ------------------------------------------------------------------
    # Properties "efectivas" — combinan override de sucursal con default
    # del artículo. Si la sucursal lo override, ése; sino el default del
    # artículo (que también puede ser None).
    # ------------------------------------------------------------------

    @property
    def efectivo_minimo(self) -> Decimal | None:
        if self.stock_minimo is not None:
            return self.stock_minimo
        return self.articulo.stock_minimo_default if self.articulo else None

    @property
    def efectivo_maximo(self) -> Decimal | None:
        if self.stock_maximo is not None:
            return self.stock_maximo
        return self.articulo.stock_maximo_default if self.articulo else None

    @property
    def efectivo_reorden(self) -> Decimal | None:
        if self.punto_reorden is not None:
            return self.punto_reorden
        return self.articulo.punto_reorden_default if self.articulo else None

    @property
    def efectivo_lead_time(self) -> int | None:
        if self.lead_time_dias is not None:
            return self.lead_time_dias
        if self.articulo and self.articulo.lead_time_dias_default is not None:
            return self.articulo.lead_time_dias_default
        if (
            self.articulo
            and self.articulo.proveedor_principal is not None
            and self.articulo.proveedor_principal.lead_time_dias_default is not None
        ):
            return self.articulo.proveedor_principal.lead_time_dias_default
        return None

    @property
    def estado_reposicion(self) -> str:
        """Devuelve estado: 'agotado' | 'critico' | 'reorden' | 'sobrestock' | 'ok'.

        - agotado: cantidad <= 0
        - critico: cantidad <= efectivo_minimo (si está seteado)
        - reorden: cantidad <= efectivo_reorden (si está seteado)
        - sobrestock: cantidad > efectivo_maximo (si está seteado)
        - ok: ninguno de los anteriores
        """
        cant = self.cantidad or Decimal("0")
        if cant <= 0:
            return "agotado"
        emin = self.efectivo_minimo
        if emin is not None and cant <= emin:
            return "critico"
        eror = self.efectivo_reorden
        if eror is not None and cant <= eror:
            return "reorden"
        emax = self.efectivo_maximo
        if emax is not None and cant > emax:
            return "sobrestock"
        return "ok"

    def __repr__(self) -> str:
        return f"<StockSucursal art={self.articulo_id} suc={self.sucursal_id} qty={self.cantidad}>"
