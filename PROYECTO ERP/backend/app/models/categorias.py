"""Taxonomía de artículos: Familia > Rubro > Subrubro, más Marca."""
from __future__ import annotations

from sqlalchemy import Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class Familia(Base, TimestampMixin):
    __tablename__ = "familias"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    rubros: Mapped[list[Rubro]] = relationship("Rubro", back_populates="familia")


class Rubro(Base, TimestampMixin):
    __tablename__ = "rubros"
    __table_args__ = (
        UniqueConstraint("familia_id", "codigo", name="uq_rubros_familia_codigo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    familia_id: Mapped[int] = mapped_column(
        ForeignKey("familias.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    familia: Mapped[Familia] = relationship("Familia", back_populates="rubros")
    subrubros: Mapped[list[Subrubro]] = relationship("Subrubro", back_populates="rubro")


class Subrubro(Base, TimestampMixin):
    __tablename__ = "subrubros"
    __table_args__ = (
        UniqueConstraint("rubro_id", "codigo", name="uq_subrubros_rubro_codigo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    rubro_id: Mapped[int] = mapped_column(
        ForeignKey("rubros.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    rubro: Mapped[Rubro] = relationship("Rubro", back_populates="subrubros")


class Marca(Base, TimestampMixin):
    __tablename__ = "marcas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nombre: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
