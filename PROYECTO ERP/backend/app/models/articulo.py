"""Modelos Articulo y ArticuloProveedor."""
from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TimestampMixin


class UnidadMedidaEnum(enum.StrEnum):
    unidad = "unidad"
    kg = "kg"
    gr = "gr"
    lt = "lt"
    ml = "ml"


class Articulo(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "articulos"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    codigo_barras: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    descripcion: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    descripcion_corta: Mapped[str | None] = mapped_column(String(100), nullable=True)

    familia_id: Mapped[int | None] = mapped_column(
        ForeignKey("familias.id", ondelete="SET NULL"), nullable=True, index=True
    )
    rubro_id: Mapped[int | None] = mapped_column(
        ForeignKey("rubros.id", ondelete="SET NULL"), nullable=True, index=True
    )
    subrubro_id: Mapped[int | None] = mapped_column(
        ForeignKey("subrubros.id", ondelete="SET NULL"), nullable=True, index=True
    )
    marca_id: Mapped[int | None] = mapped_column(
        ForeignKey("marcas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    proveedor_principal_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True, index=True
    )

    unidad_medida: Mapped[UnidadMedidaEnum] = mapped_column(
        Enum(UnidadMedidaEnum, name="unidad_medida_enum"),
        nullable=False,
        default=UnidadMedidaEnum.unidad,
    )
    controla_stock: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    controla_vencimiento: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    costo: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    pvp_base: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    iva_porc: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False, default=Decimal("21"))

    # Stock inteligente — defaults globales por artículo (opción C).
    # Cada (artículo × sucursal) puede sobreescribir estos valores.
    stock_minimo_default: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    stock_maximo_default: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    punto_reorden_default: Mapped[Decimal | None] = mapped_column(
        Numeric(14, 4), nullable=True
    )
    lead_time_dias_default: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    familia = relationship("Familia")
    rubro = relationship("Rubro")
    subrubro = relationship("Subrubro")
    marca = relationship("Marca")
    proveedor_principal = relationship("Proveedor", foreign_keys=[proveedor_principal_id])
    proveedores: Mapped[list[ArticuloProveedor]] = relationship(
        "ArticuloProveedor", back_populates="articulo", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Articulo {self.codigo} {self.descripcion[:30]}>"


class ArticuloProveedor(Base, TimestampMixin):
    __tablename__ = "articulo_proveedores"
    __table_args__ = (
        UniqueConstraint("articulo_id", "proveedor_id", name="uq_artprov_art_prov"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    articulo_id: Mapped[int] = mapped_column(
        ForeignKey("articulos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    proveedor_id: Mapped[int] = mapped_column(
        ForeignKey("proveedores.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    codigo_proveedor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    costo_proveedor: Mapped[Decimal] = mapped_column(Numeric(14, 4), nullable=False, default=0)
    ultimo_ingreso: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    articulo: Mapped[Articulo] = relationship("Articulo", back_populates="proveedores")
    proveedor = relationship("Proveedor")
