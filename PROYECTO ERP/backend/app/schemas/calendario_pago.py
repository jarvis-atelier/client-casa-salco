"""Schemas Pydantic para Calendario de pagos."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.calendario_pago import (
    EstadoCompromisoEnum,
    TipoCompromisoEnum,
)


# ---------------------------------------------------------------------------
# Tarjeta corporativa
# ---------------------------------------------------------------------------


class TarjetaCorporativaCreate(BaseModel):
    nombre: str = Field(min_length=1, max_length=100)
    banco: str | None = Field(default=None, max_length=100)
    ultimos_4: str = Field(min_length=4, max_length=4)
    titular: str | None = Field(default=None, max_length=150)
    limite_total: Decimal | None = None
    dia_cierre: int = Field(ge=1, le=31)
    dia_vencimiento: int = Field(ge=1, le=31)
    activa: bool = True


class TarjetaCorporativaPatch(BaseModel):
    nombre: str | None = Field(default=None, max_length=100)
    banco: str | None = Field(default=None, max_length=100)
    ultimos_4: str | None = Field(default=None, min_length=4, max_length=4)
    titular: str | None = Field(default=None, max_length=150)
    limite_total: Decimal | None = None
    dia_cierre: int | None = Field(default=None, ge=1, le=31)
    dia_vencimiento: int | None = Field(default=None, ge=1, le=31)
    activa: bool | None = None


class TarjetaCorporativaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nombre: str
    banco: str | None
    ultimos_4: str
    titular: str | None
    limite_total: Decimal | None
    dia_cierre: int
    dia_vencimiento: int
    activa: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Pagos
# ---------------------------------------------------------------------------


class PagoCompromisoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    compromiso_id: int
    fecha_pago: date
    monto: Decimal
    medio_pago: str
    referencia: str | None
    movimiento_caja_id: int | None
    user_id: int
    created_at: datetime


class PagoCompromisoCreate(BaseModel):
    monto: Decimal = Field(gt=Decimal("0"))
    fecha_pago: date
    medio_pago: str = Field(min_length=1, max_length=50)
    referencia: str | None = Field(default=None, max_length=200)
    registrar_movimiento_caja: bool = False
    sucursal_id: int | None = None


# ---------------------------------------------------------------------------
# Compromiso
# ---------------------------------------------------------------------------


class CompromisoPagoCreate(BaseModel):
    tipo: TipoCompromisoEnum
    descripcion: str = Field(min_length=1, max_length=255)
    monto_total: Decimal = Field(gt=Decimal("0"))
    fecha_emision: date | None = None
    fecha_vencimiento: date
    proveedor_id: int | None = None
    factura_id: int | None = None
    tarjeta_id: int | None = None
    sucursal_id: int | None = None
    nota: str | None = None


class CompromisoPagoPatch(BaseModel):
    tipo: TipoCompromisoEnum | None = None
    descripcion: str | None = Field(default=None, max_length=255)
    monto_total: Decimal | None = None
    fecha_emision: date | None = None
    fecha_vencimiento: date | None = None
    proveedor_id: int | None = None
    factura_id: int | None = None
    tarjeta_id: int | None = None
    sucursal_id: int | None = None
    nota: str | None = None
    estado: EstadoCompromisoEnum | None = None


class CompromisoPagoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    tipo: TipoCompromisoEnum
    estado: EstadoCompromisoEnum
    descripcion: str
    monto_total: Decimal
    monto_pagado: Decimal
    fecha_emision: date | None
    fecha_vencimiento: date
    fecha_pago_real: date | None
    proveedor_id: int | None
    factura_id: int | None
    tarjeta_id: int | None
    sucursal_id: int | None
    creado_por_user_id: int
    pagado_por_user_id: int | None
    nota: str | None
    created_at: datetime
    updated_at: datetime


class CompromisoPagoDetalleOut(CompromisoPagoOut):
    pagos: list[PagoCompromisoOut] = []
    proveedor_nombre: str | None = None
    tarjeta_nombre: str | None = None


class CompromisoResumen(BaseModel):
    vencidos: int
    vence_hoy: int
    esta_semana: int
    este_mes: int
    total_pendiente: Decimal
    total_vencido: Decimal


class CalendarDayOut(BaseModel):
    fecha: date
    cantidad: int
    monto_total: Decimal
    severidad_max: str  # "critica" | "alta" | "media" | "baja"
    compromisos_ids: list[int]


class AutoGenerarResult(BaseModel):
    creados: int
    desde_facturas: int
    desde_tarjetas: int
