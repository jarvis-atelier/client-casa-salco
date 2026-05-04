"""Modelos PrecioSucursal y PrecioHistorico — sync precios multi-sucursal + auditoría."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class PrecioSucursal(Base, TimestampMixin):
    """Precio vigente de un artículo en una sucursal puntual.

    Un solo precio activo a la vez por (articulo, sucursal). La lógica de
    "cerrar" el anterior y abrir uno nuevo se maneja en el servicio.
    """

    __tablename__ = "precios_sucursal"
    __table_args__ = (
        # Índice parcial — solo un registro activo=true por (articulo, sucursal).
        # Postgres y SQLite soportan partial indexes con WHERE.
        Index(
            "uq_precio_sucursal_activo",
            "articulo_id",
            "sucursal_id",
            unique=True,
            sqlite_where=text("activo = 1"),
            postgresql_where=text("activo = true"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    articulo_id: Mapped[int] = mapped_column(
        ForeignKey("articulos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sucursal_id: Mapped[int] = mapped_column(
        ForeignKey("sucursales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    precio: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    vigente_desde: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    vigente_hasta: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    articulo = relationship("Articulo")
    sucursal = relationship("Sucursal")
    updated_by = relationship("User")


class PrecioHistorico(Base):
    """Append-only. Guarda cada cambio de precio para auditoría."""

    __tablename__ = "precios_historicos"

    id: Mapped[int] = mapped_column(primary_key=True)
    articulo_id: Mapped[int] = mapped_column(
        ForeignKey("articulos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sucursal_id: Mapped[int | None] = mapped_column(
        ForeignKey("sucursales.id", ondelete="SET NULL"), nullable=True, index=True
    )
    precio_anterior: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    precio_nuevo: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False)
    cambiado_por_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    motivo: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    articulo = relationship("Articulo")
    sucursal = relationship("Sucursal")
    cambiado_por = relationship("User")
