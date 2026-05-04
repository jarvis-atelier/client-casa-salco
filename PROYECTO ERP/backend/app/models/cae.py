"""Modelo Cae — registro de CAE (Codigo de Autorizacion Electronica) emitido por AFIP.

Cada factura que requiere CAE genera exactamente UN registro aqui. Es el audit log
regulatorio (retencion 10 anios por RG 5409).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, TimestampMixin


class Cae(Base, TimestampMixin):
    """Un CAE por factura. Unique sobre factura_id para garantizarlo."""

    __tablename__ = "caes"

    id: Mapped[int] = mapped_column(primary_key=True)

    # FK a Factura (lo crea 2.1). Usamos string reference para evitar import circular
    # si Factura se carga en otro orden.
    factura_id: Mapped[int] = mapped_column(
        ForeignKey("facturas.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,  # un CAE por factura
        index=True,
    )

    # CUIT del emisor (del comercio, no del cliente) — formato sin guiones o con guiones.
    cuit_emisor: Mapped[str] = mapped_column(String(13), nullable=False, index=True)

    # Codigo AFIP del tipo de comprobante:
    # 1=FactA, 6=FactB, 11=FactC, 2=NDebA, 7=NDebB, 12=NDebC,
    # 3=NCreA, 8=NCreB, 13=NCreC, 201-213=FCE MiPyMEs, etc.
    tipo_afip: Mapped[int] = mapped_column(Integer, nullable=False)
    punto_venta: Mapped[int] = mapped_column(Integer, nullable=False)
    numero: Mapped[int] = mapped_column(Integer, nullable=False)

    # CAE: codigo de 14 digitos emitido por AFIP.
    cae: Mapped[str] = mapped_column(String(14), nullable=False, index=True)
    fecha_vencimiento: Mapped[date] = mapped_column(Date, nullable=False)
    fecha_emision: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=datetime.utcnow
    )

    # Proveedor que genero el CAE — "mock" para dev, "pyafipws" para prod.
    # Util para debug / auditoria post-migracion.
    proveedor: Mapped[str] = mapped_column(String(30), nullable=False, default="mock")

    # Snapshot del XML request/response para auditoria regulatoria (RG 5409 — 10 anios).
    request_xml: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_xml: Mapped[str | None] = mapped_column(Text, nullable=True)

    # URL del QR AFIP segun spec https://www.afip.gob.ar/fe/qr/
    qr_url: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Observaciones AFIP (si las hay — RG 5616 puede generar observaciones).
    obs_afip: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Resultado AFIP: A=Aprobado, R=Rechazado, P=Parcial, X=Observado.
    resultado: Mapped[str] = mapped_column(String(1), nullable=False, default="A")
    # Indicador de reproceso: S=Si (reintento autorizado), N=No.
    reproceso: Mapped[str] = mapped_column(String(1), nullable=False, default="N")

    def __repr__(self) -> str:
        return f"<Cae {self.cae} factura={self.factura_id} resultado={self.resultado}>"
