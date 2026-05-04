"""Schemas Pydantic para Alerta."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.alerta import EstadoAlertaEnum, SeveridadEnum, TipoAlertaEnum


class AlertaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoAlertaEnum
    severidad: SeveridadEnum
    estado: EstadoAlertaEnum
    titulo: str
    descripcion: str
    contexto: dict[str, Any]

    factura_id: int | None
    user_relacionado_id: int | None
    proveedor_id: int | None
    sucursal_id: int | None

    detected_at: datetime
    resolved_at: datetime | None
    resolved_by_user_id: int | None
    nota_resolucion: str | None

    deteccion_hash: str
    created_at: datetime
    updated_at: datetime


class AlertaDetalleOut(AlertaOut):
    """Versión enriquecida con los datos de las entidades relacionadas."""

    factura: dict[str, Any] | None = None
    user_relacionado: dict[str, Any] | None = None
    proveedor: dict[str, Any] | None = None
    sucursal: dict[str, Any] | None = None


class AlertaPatch(BaseModel):
    estado: EstadoAlertaEnum | None = None
    nota_resolucion: str | None = None


class AlertaResumen(BaseModel):
    nuevas: int
    en_revision: int
    criticas: int
    ultimas_24h: int
    total_abiertas: int


class AlertaRunResult(BaseModel):
    creadas: int
    detectores: int
    detalle: dict[str, int]
