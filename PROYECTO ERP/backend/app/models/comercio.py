"""Modelo ComercioConfig — datos del comercio (singleton).

Es la configuración global de la organización: razón social, CUIT, IIBB,
domicilio, etc. Va en el header de tickets/facturas y en otros documentos.

Convención: solo existe la fila id=1. Los endpoints crean defaults vacíos al
primer GET si no existe.
"""
from __future__ import annotations

from datetime import date

from sqlalchemy import Date, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class ComercioConfig(Base, TimestampMixin):
    __tablename__ = "comercio_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    razon_social: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    nombre_fantasia: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cuit: Mapped[str] = mapped_column(String(13), nullable=False, default="")
    condicion_iva: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    domicilio: Mapped[str | None] = mapped_column(String(200), nullable=True)
    localidad: Mapped[str | None] = mapped_column(String(100), nullable=True)
    provincia: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cp: Mapped[str | None] = mapped_column(String(10), nullable=True)
    telefono: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(120), nullable=True)
    iibb: Mapped[str | None] = mapped_column(String(50), nullable=True)
    inicio_actividades: Mapped[date | None] = mapped_column(Date, nullable=True)
    logo_path: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pie_ticket: Mapped[str | None] = mapped_column(String(255), nullable=True)

    def __repr__(self) -> str:
        return f"<ComercioConfig {self.razon_social or '(sin nombre)'} cuit={self.cuit or '-'}>"
