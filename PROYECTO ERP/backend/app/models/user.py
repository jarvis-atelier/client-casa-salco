"""Modelo User — autenticación y roles."""
from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .sucursal import Sucursal


class RolEnum(enum.StrEnum):
    admin = "admin"
    supervisor = "supervisor"
    cajero = "cajero"
    fiambrero = "fiambrero"
    repositor = "repositor"
    contador = "contador"


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    rol: Mapped[RolEnum] = mapped_column(
        Enum(RolEnum, name="rol_enum"), nullable=False, default=RolEnum.cajero
    )
    sucursal_id: Mapped[int | None] = mapped_column(
        ForeignKey("sucursales.id", ondelete="SET NULL"), nullable=True
    )
    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    sucursal: Mapped[Sucursal | None] = relationship("Sucursal", back_populates="users")

    def __repr__(self) -> str:
        return f"<User {self.email} rol={self.rol.value}>"
