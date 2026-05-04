"""Schemas Pydantic para OCR de comprobantes."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.comprobante_ocr import EstadoOcrEnum, TipoComprobanteOcrEnum


class OcrItemExtraido(BaseModel):
    """Item extraído por la IA. Todos los campos son sugerencias editables."""

    model_config = ConfigDict(from_attributes=True)

    descripcion: str
    cantidad: Decimal = Field(default=Decimal("1"))
    unidad: str = Field(default="unidad")
    precio_unitario: Decimal = Field(default=Decimal("0"))
    subtotal: Decimal = Field(default=Decimal("0"))
    articulo_id_match: int | None = None


class ProveedorMatchOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    razon_social: str
    cuit: str | None = None


class FacturaResumenOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    numero: int
    punto_venta: int
    tipo: str
    total: Decimal


class ComprobanteOcrOut(BaseModel):
    """Salida estándar del OCR."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    estado: EstadoOcrEnum
    tipo_detectado: TipoComprobanteOcrEnum
    letra: str | None = None
    confianza: Decimal | None = None

    archivo_path: str
    archivo_size_bytes: int
    archivo_mime: str

    proveedor_nombre_raw: str | None = None
    proveedor_cuit_raw: str | None = None
    proveedor_id_match: int | None = None
    proveedor_match: ProveedorMatchOut | None = None

    numero_comprobante: str | None = None
    fecha_comprobante: date | None = None

    subtotal: Decimal | None = None
    iva_total: Decimal | None = None
    total: Decimal | None = None

    items_extraidos: list[dict] = []
    error_message: str | None = None

    uploaded_by_user_id: int
    sucursal_id: int | None = None
    factura_creada_id: int | None = None
    factura_creada: FacturaResumenOut | None = None

    duracion_extraccion_ms: int | None = None
    modelo_ia_usado: str | None = None

    created_at: datetime
    updated_at: datetime


class OcrItemOverride(BaseModel):
    """Item editado por el usuario antes de confirmar."""

    descripcion: str
    cantidad: Decimal = Field(gt=0)
    unidad: str = Field(default="unidad")
    precio_unitario: Decimal = Field(ge=0)
    iva_porc: Decimal = Field(default=Decimal("21"), ge=0, le=100)
    descuento_porc: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    articulo_id: int | None = None  # si null y crear_articulo_si_falta → crea uno
    crear_articulo_si_falta: bool = True


class OcrConfirmarPayload(BaseModel):
    sucursal_id: int
    proveedor_id: int | None = None
    numero_override: str | None = None
    fecha_override: date | None = None
    observacion: str | None = None
    items: list[OcrItemOverride] = Field(min_length=1)
