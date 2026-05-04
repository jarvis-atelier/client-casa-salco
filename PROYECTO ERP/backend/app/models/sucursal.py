"""Modelos Sucursal y Area (organización física del negocio)."""
from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, SoftDeleteMixin, TimestampMixin

if TYPE_CHECKING:
    from .user import User


class Sucursal(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "sucursales"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    direccion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ciudad: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provincia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    lat: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    lng: Mapped[Decimal | None] = mapped_column(Numeric(10, 7), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(50), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    areas: Mapped[list[Area]] = relationship(
        "Area", back_populates="sucursal", cascade="all, delete-orphan"
    )
    users: Mapped[list[User]] = relationship("User", back_populates="sucursal")

    def __repr__(self) -> str:
        return f"<Sucursal {self.codigo} {self.nombre}>"


class Area(Base, TimestampMixin):
    __tablename__ = "areas"
    __table_args__ = (
        UniqueConstraint("sucursal_id", "codigo", name="uq_areas_sucursal_codigo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    sucursal_id: Mapped[int] = mapped_column(
        ForeignKey("sucursales.id", ondelete="CASCADE"), nullable=False, index=True
    )
    nombre: Mapped[str] = mapped_column(String(100), nullable=False)
    codigo: Mapped[str] = mapped_column(String(20), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activa: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    orden: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    sucursal: Mapped[Sucursal] = relationship("Sucursal", back_populates="areas")

    def __repr__(self) -> str:
        return f"<Area {self.codigo} suc={self.sucursal_id}>"
