"""Modelo Alerta — alertas de inconsistencias detectadas automáticamente.

Cada alerta tiene un `deteccion_hash` determinístico que evita duplicarla en
re-ejecuciones del runner (idempotencia).
"""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin


class TipoAlertaEnum(enum.StrEnum):
    pago_duplicado = "pago_duplicado"
    factura_compra_repetida = "factura_compra_repetida"
    items_repetidos_diff_nro = "items_repetidos_diff_nro"
    anulaciones_frecuentes = "anulaciones_frecuentes"
    ajuste_stock_sospechoso = "ajuste_stock_sospechoso"
    nota_credito_sospechosa = "nota_credito_sospechosa"
    venta_fuera_horario = "venta_fuera_horario"
    descuento_excesivo = "descuento_excesivo"
    vencimiento_proximo = "vencimiento_proximo"
    # Stock inteligente — opción C
    stock_bajo_minimo = "stock_bajo_minimo"
    sobrestock = "sobrestock"
    rotacion_lenta = "rotacion_lenta"
    rotacion_rapida_faltante = "rotacion_rapida_faltante"


class SeveridadEnum(enum.StrEnum):
    baja = "baja"
    media = "media"
    alta = "alta"
    critica = "critica"


class EstadoAlertaEnum(enum.StrEnum):
    nueva = "nueva"
    en_revision = "en_revision"
    descartada = "descartada"
    confirmada = "confirmada"
    resuelta = "resuelta"


class Alerta(Base, TimestampMixin):
    """Alerta de inconsistencia operativa.

    El `deteccion_hash` es único: cada detector arma un hash determinístico
    de los datos que dispararon la alerta. Si vuelve a correr y encuentra el
    mismo patrón, no duplica la alerta.
    """

    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(primary_key=True)
    tipo: Mapped[TipoAlertaEnum] = mapped_column(
        Enum(TipoAlertaEnum, name="tipo_alerta_enum"),
        nullable=False,
        index=True,
    )
    severidad: Mapped[SeveridadEnum] = mapped_column(
        Enum(SeveridadEnum, name="severidad_enum"),
        nullable=False,
        default=SeveridadEnum.media,
        index=True,
    )
    estado: Mapped[EstadoAlertaEnum] = mapped_column(
        Enum(EstadoAlertaEnum, name="estado_alerta_enum"),
        nullable=False,
        default=EstadoAlertaEnum.nueva,
        index=True,
    )
    titulo: Mapped[str] = mapped_column(String(200), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    contexto: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Referencias opcionales — la alerta puede apuntar a una factura, un user,
    # un proveedor o una sucursal específica para dar contexto en la UI.
    factura_id: Mapped[int | None] = mapped_column(
        ForeignKey("facturas.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_relacionado_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    proveedor_id: Mapped[int | None] = mapped_column(
        ForeignKey("proveedores.id", ondelete="SET NULL"), nullable=True, index=True
    )
    sucursal_id: Mapped[int | None] = mapped_column(
        ForeignKey("sucursales.id", ondelete="SET NULL"), nullable=True, index=True
    )

    detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    nota_resolucion: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Hash único para idempotencia
    deteccion_hash: Mapped[str] = mapped_column(
        String(64), unique=True, nullable=False, index=True
    )

    factura = relationship("Factura", foreign_keys=[factura_id])
    user_relacionado = relationship("User", foreign_keys=[user_relacionado_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_user_id])
    proveedor = relationship("Proveedor", foreign_keys=[proveedor_id])
    sucursal = relationship("Sucursal", foreign_keys=[sucursal_id])

    def __repr__(self) -> str:
        return (
            f"<Alerta {self.tipo.value} sev={self.severidad.value} "
            f"estado={self.estado.value} id={self.id}>"
        )
