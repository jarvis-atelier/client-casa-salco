"""Schemas Pydantic para PrecioSucursal y operación de actualización multi-sucursal."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PrecioSucursalOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    articulo_id: int
    sucursal_id: int
    precio: Decimal
    vigente_desde: datetime
    vigente_hasta: datetime | None
    activo: bool
    updated_by_user_id: int | None


class PrecioSucursalItem(BaseModel):
    sucursal_id: int
    precio: Decimal = Field(gt=0)


class PrecioUpdateRequest(BaseModel):
    """Request para actualización de precios.

    Soporta dos formas (equivalentes):

    1) Explícita por sucursal:
       {
         "articulo_id": 1,
         "motivo": "ajuste semanal",
         "cambios": [{"sucursal_id": 1, "precio": "100"}, ...]
       }
       (`sucursales` se acepta como alias de `cambios` por compat.)

    2) Aplicar a todas las sucursales activas:
       {
         "articulo_id": 1,
         "motivo": "...",
         "precio": "100",
         "aplicar_a_todas": true
       }
       El servicio expande esto a un cambio por cada sucursal activa.
    """

    articulo_id: int
    motivo: str | None = Field(default=None, max_length=255)

    # Forma 1 — lista explícita (`cambios` nuevo, `sucursales` alias legado)
    cambios: list[PrecioSucursalItem] | None = None
    sucursales: list[PrecioSucursalItem] | None = None

    # Forma 2 — precio único aplicado a todas
    precio: Decimal | None = Field(default=None, gt=0)
    aplicar_a_todas: bool = False

    @model_validator(mode="after")
    def _check_body(self) -> "PrecioUpdateRequest":
        tiene_lista = bool(self.cambios) or bool(self.sucursales)
        if self.aplicar_a_todas:
            if self.precio is None:
                raise ValueError(
                    "aplicar_a_todas=true requiere campo 'precio'"
                )
            if tiene_lista:
                raise ValueError(
                    "aplicar_a_todas no se puede combinar con cambios/sucursales"
                )
            return self
        if not tiene_lista:
            raise ValueError(
                "debe enviar 'cambios' (lista) o 'aplicar_a_todas' con 'precio'"
            )
        # Normalizar alias: si vino `sucursales` lo copiamos a `cambios`.
        if self.cambios is None and self.sucursales is not None:
            self.cambios = self.sucursales
        return self


class PrecioActualizadoItem(BaseModel):
    sucursal_id: int
    precio_anterior: str | None
    precio_nuevo: str


class PrecioUpdateResponse(BaseModel):
    articulo_id: int
    actualizados: int
    items: list[PrecioActualizadoItem]


class SucursalRef(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    codigo: str
    nombre: str


class PrecioListadoItem(BaseModel):
    """Shape del GET /precios?articulo_id=N — un item por sucursal con precio activo."""

    sucursal: SucursalRef
    precio: str
    vigente_desde: datetime
