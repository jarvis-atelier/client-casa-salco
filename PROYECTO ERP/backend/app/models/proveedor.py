"""Modelo Proveedor."""
from __future__ import annotations

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, SoftDeleteMixin, TimestampMixin


class Proveedor(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "proveedores"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False)
    cuit: Mapped[str | None] = mapped_column(String(15), nullable=True, index=True)
    telefono: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(255), nullable=True)
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # Stock inteligente — opción C
    # Lead time default del proveedor (días entre OC y recepción).
    # Cada (articulo, sucursal) puede sobreescribirlo.
    lead_time_dias_default: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )

    def __repr__(self) -> str:
        return f"<Proveedor {self.codigo} {self.razon_social}>"
