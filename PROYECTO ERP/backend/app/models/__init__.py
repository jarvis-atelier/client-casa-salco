"""Modelos SQLAlchemy del sistema.

Importar TODO desde aquí para que Alembic descubra el metadata completo.
"""
from .alerta import (
    Alerta,
    EstadoAlertaEnum,
    SeveridadEnum,
    TipoAlertaEnum,
)
from .articulo import Articulo, ArticuloProveedor, UnidadMedidaEnum
from .base import Base, SoftDeleteMixin, TimestampMixin
from .cae import Cae
from .calendario_pago import (
    CompromisoPago,
    EstadoCompromisoEnum,
    PagoCompromiso,
    TarjetaCorporativa,
    TipoCompromisoEnum,
)
from .categorias import Familia, Marca, Rubro, Subrubro
from .cliente import Cliente, CondicionIvaEnum
from .comercio import ComercioConfig
from .comprobante_ocr import (
    ComprobanteOcr,
    EstadoOcrEnum,
    TipoComprobanteOcrEnum,
)
from .factura import (
    EstadoComprobanteEnum,
    Factura,
    TipoComprobanteEnum,
)
from .factura_item import FacturaItem
from .pago import FacturaPago, MedioPagoEnum
from .precio import PrecioHistorico, PrecioSucursal
from .proveedor import Proveedor
from .resumen import MovimientoCaja, TipoMovimientoEnum
from .stock import StockSucursal
from .sucursal import Area, Sucursal
from .user import RolEnum, User

__all__ = [
    "Alerta",
    "Area",
    "Articulo",
    "ArticuloProveedor",
    "Base",
    "Cae",
    "Cliente",
    "ComercioConfig",
    "ComprobanteOcr",
    "CompromisoPago",
    "CondicionIvaEnum",
    "EstadoAlertaEnum",
    "EstadoComprobanteEnum",
    "EstadoCompromisoEnum",
    "EstadoOcrEnum",
    "Factura",
    "FacturaItem",
    "FacturaPago",
    "Familia",
    "Marca",
    "MedioPagoEnum",
    "MovimientoCaja",
    "PagoCompromiso",
    "PrecioHistorico",
    "PrecioSucursal",
    "Proveedor",
    "RolEnum",
    "Rubro",
    "SeveridadEnum",
    "SoftDeleteMixin",
    "StockSucursal",
    "Subrubro",
    "Sucursal",
    "TarjetaCorporativa",
    "TimestampMixin",
    "TipoAlertaEnum",
    "TipoComprobanteEnum",
    "TipoComprobanteOcrEnum",
    "TipoCompromisoEnum",
    "TipoMovimientoEnum",
    "UnidadMedidaEnum",
    "User",
]
