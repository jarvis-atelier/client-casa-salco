"""Detectores concretos de patrones sospechosos."""
from .ajuste_stock_sospechoso import AjusteStockSospechosoDetector
from .anulaciones_frecuentes import AnulacionesFrecuentesDetector
from .factura_compra_repetida import FacturaCompraRepetidaDetector
from .items_repetidos_diff_nro import ItemsRepetidosDiffNroDetector
from .pago_duplicado import PagoDuplicadoDetector
from .rotacion_lenta import RotacionLentaDetector
from .rotacion_rapida_faltante import RotacionRapidaFaltanteDetector
from .sobrestock import SobrestockDetector
from .stock_bajo_minimo import StockBajoMinimoDetector
from .vencimiento_proximo import VencimientoProximoDetector

__all__ = [
    "AjusteStockSospechosoDetector",
    "AnulacionesFrecuentesDetector",
    "FacturaCompraRepetidaDetector",
    "ItemsRepetidosDiffNroDetector",
    "PagoDuplicadoDetector",
    "RotacionLentaDetector",
    "RotacionRapidaFaltanteDetector",
    "SobrestockDetector",
    "StockBajoMinimoDetector",
    "VencimientoProximoDetector",
]
