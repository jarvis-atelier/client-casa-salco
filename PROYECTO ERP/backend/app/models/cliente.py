"""Modelo Cliente."""
from __future__ import annotations

import enum
from decimal import Decimal

from sqlalchemy import Boolean, Enum, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, SoftDeleteMixin, TimestampMixin


class CondicionIvaEnum(enum.StrEnum):
    responsable_inscripto = "responsable_inscripto"
    monotributo = "monotributo"
    consumidor_final = "consumidor_final"
    exento = "exento"
    no_categorizado = "no_categorizado"


class Cliente(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "clientes"

    id: Mapped[int] = mapped_column(primary_key=True)
    codigo: Mapped[str] = mapped_column(String(30), unique=True, nullable=False, index=True)
    razon_social: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    cuit: Mapped[str | None] = mapped_column(String(15), nullable=True, index=True)
    condicion_iva: Mapped[CondicionIvaEnum] = mapped_column(
        Enum(CondicionIvaEnum, name="condicion_iva_enum"),
        nullable=False,
        default=CondicionIvaEnum.consumidor_final,
    )
    # Para RG 5616 (codigos de AFIP para condicion del receptor).
    condicion_iva_receptor_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    telefono: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    direccion: Mapped[str | None] = mapped_column(String(255), nullable=True)

    cuenta_corriente: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    limite_cuenta_corriente: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=0
    )
    saldo: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)

    activo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<Cliente {self.codigo} {self.razon_social}>"
