"""Modelo ComprobanteOcr — comprobantes (factura/remito/presupuesto) leídos por IA Vision.

Un ComprobanteOcr es un *borrador* extraído de una imagen subida por el usuario.
Su ciclo de vida:

    pendiente → procesando → extraido → confirmado (crea Factura compra)
                                     └→ descartado
                          └→ error

Cuando el user confirma, se crea una `Factura` tipo `factura_c` (compra) con sus
items. La referencia queda en `factura_creada_id`.
"""
from __future__ import annotations

import enum
from datetime import date
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Date,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class EstadoOcrEnum(str, enum.Enum):
    pendiente = "pendiente"      # subido, falta procesar
    procesando = "procesando"    # llamada a Vision en curso
    extraido = "extraido"        # IA respondió, esperando confirmación humana
    confirmado = "confirmado"    # user confirmó → factura compra creada
    descartado = "descartado"    # user descartó
    error = "error"              # falló la extracción


class TipoComprobanteOcrEnum(str, enum.Enum):
    factura = "factura"
    remito = "remito"
    presupuesto = "presupuesto"
    desconocido = "desconocido"


class ComprobanteOcr(Base, TimestampMixin):
    __tablename__ = "comprobantes_ocr"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Archivo
    archivo_path: Mapped[str] = mapped_column(String(500), nullable=False)
    archivo_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    archivo_mime: Mapped[str] = mapped_column(String(50), nullable=False, default="image/jpeg")

    # Estado y tipo
    estado: Mapped[EstadoOcrEnum] = mapped_column(
        Enum(EstadoOcrEnum, name="estado_ocr_enum"),
        nullable=False,
        default=EstadoOcrEnum.pendiente,
        index=True,
    )
    tipo_detectado: Mapped[TipoComprobanteOcrEnum] = mapped_column(
        Enum(TipoComprobanteOcrEnum, name="tipo_comprobante_ocr_enum"),
        nullable=False,
        default=TipoComprobanteOcrEnum.desconocido,
    )
    letra: Mapped[str | None] = mapped_column(String(2), nullable=True)
    confianza: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )

    # Datos extraídos por Vision (todo nullable hasta que la IA responda)
    proveedor_nombre_raw: Mapped[str | None] = mapped_column(String(255), nullable=True)
    proveedor_cuit_raw: Mapped[str | None] = mapped_column(String(20), nullable=True)
    proveedor_id_match: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True, index=True
    )

    numero_comprobante: Mapped[str | None] = mapped_column(String(40), nullable=True)
    fecha_comprobante: Mapped[date | None] = mapped_column(Date, nullable=True)

    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    iva_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)

    # Items extraídos: lista de dicts JSON.
    items_extraidos: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    raw_response: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Audit
    uploaded_by_user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    sucursal_id: Mapped[int | None] = mapped_column(
        ForeignKey("sucursales.id", ondelete="SET NULL"), nullable=True, index=True
    )
    factura_creada_id: Mapped[int | None] = mapped_column(
        ForeignKey("facturas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    duracion_extraccion_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    modelo_ia_usado: Mapped[str | None] = mapped_column(String(80), nullable=True)

    # Relaciones
    proveedor_match = relationship("Proveedor")
    sucursal = relationship("Sucursal")
    factura_creada = relationship("Factura")
    uploaded_by = relationship("User")

    def __repr__(self) -> str:
        return (
            f"<ComprobanteOcr id={self.id} estado={self.estado.value} "
            f"tipo={self.tipo_detectado.value}>"
        )
