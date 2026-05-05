"""Modelo ArticuloCodigo: tabla 1:N de códigos por artículo (principal/alterno/empaquetado/interno)."""
from __future__ import annotations

import enum
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, TimestampMixin

if TYPE_CHECKING:
    from .articulo import Articulo


class TipoCodigoArticuloEnum(enum.StrEnum):
    principal = "principal"
    alterno = "alterno"
    empaquetado = "empaquetado"
    interno = "interno"


class ArticuloCodigo(Base, TimestampMixin):
    __tablename__ = "articulo_codigos"
    __table_args__ = (
        UniqueConstraint("articulo_id", "codigo", name="uq_articulo_codigo"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    articulo_id: Mapped[int] = mapped_column(
        ForeignKey("articulos.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    codigo: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    tipo: Mapped[TipoCodigoArticuloEnum] = mapped_column(
        Enum(TipoCodigoArticuloEnum, name="tipo_codigo_articulo_enum"),
        nullable=False,
        default=TipoCodigoArticuloEnum.principal,
    )

    articulo: Mapped[Articulo] = relationship("Articulo", back_populates="codigos")

    def __repr__(self) -> str:
        return f"<ArticuloCodigo art={self.articulo_id} {self.tipo.value}:{self.codigo}>"
