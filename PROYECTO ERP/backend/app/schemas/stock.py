"""Schemas Pydantic para StockSucursal."""
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class StockArticuloEmbedded(BaseModel):
    """Subset del Articulo embebido en respuestas de stock para evitar el
    fetch masivo del catálogo desde el frontend."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    descripcion: str
    costo: Decimal | None = None
    pvp_base: Decimal | None = None


class StockSucursalOut(BaseModel):
    """Stock con todos los campos persistidos.

    Los campos `efectivo_*` son resueltos desde el modelo (override sucursal o
    default articulo). El frontend los usa para mostrar valores efectivos sin
    tener que hacer fallback en el cliente.
    """

    model_config = ConfigDict(from_attributes=True)

    id: int
    articulo_id: int
    sucursal_id: int
    cantidad: Decimal

    # Override por sucursal (puede ser None — heredan del articulo)
    stock_minimo: Decimal | None = None
    stock_maximo: Decimal | None = None
    punto_reorden: Decimal | None = None
    lead_time_dias: int | None = None
    stock_optimo_calculado: Decimal | None = None
    ultima_recalculacion: datetime | None = None

    # Resueltos (sucursal -> articulo default)
    efectivo_minimo: Decimal | None = None
    efectivo_maximo: Decimal | None = None
    efectivo_reorden: Decimal | None = None
    efectivo_lead_time: int | None = None
    estado_reposicion: str | None = None

    # Articulo embebido — evita fetch separado del catálogo en el frontend.
    articulo: StockArticuloEmbedded | None = None

    created_at: datetime
    updated_at: datetime


class StockResumen(BaseModel):
    """Conteos por estado de reposición para una sucursal."""

    total: int
    agotado: int
    critico: int
    reorden: int
    sobrestock: int
    ok: int


class StockAjusteRequest(BaseModel):
    """Ajuste manual de stock — admin only.

    Acepta cantidad nueva (obligatoria) + opcionalmente parámetros del stock
    inteligente para overridear desde la misma UI sin un endpoint aparte.
    Pasar `None` deja el campo igual; explícitamente pasar el valor lo
    actualiza. Para "limpiar" un override, pasar string vacío no — usar
    `unset_*=true` para remover el override.
    """

    articulo_id: int
    sucursal_id: int
    cantidad_nueva: Decimal = Field(ge=0)
    motivo: str = Field(min_length=1, max_length=200)

    # Stock inteligente — todos opcionales
    stock_minimo: Decimal | None = Field(default=None, ge=0)
    stock_maximo: Decimal | None = Field(default=None, ge=0)
    punto_reorden: Decimal | None = Field(default=None, ge=0)
    lead_time_dias: int | None = Field(default=None, ge=0)

    # Si true, se setea el campo a NULL (hereda del articulo).
    unset_stock_minimo: bool = False
    unset_stock_maximo: bool = False
    unset_punto_reorden: bool = False
    unset_lead_time_dias: bool = False
