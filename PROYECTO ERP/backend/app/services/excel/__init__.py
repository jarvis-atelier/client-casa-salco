"""Builders de exportaciones Excel — para contador y reporting interno.

Cada builder genera un .xlsx en memoria (`io.BytesIO`) y devuelve los bytes
listos para enviar como `Content-Disposition: attachment`.

Convenciones:
- Cabecera bold con `PatternFill` (Apple-grey claro).
- Freeze pane fila 1.
- Currency en formato `$#,##0.00` (NamedStyle `currency_ars`).
- Fecha en formato `yyyy-mm-dd`.
- Auto width: estimamos ancho leyendo longitud de la cell más larga por columna.

Las funciones públicas devuelven `bytes`, no escriben a disco.
"""
from .builders import (
    build_cobranzas_export,
    build_compras_export,
    build_cta_cte_cliente_export,
    build_cta_cte_proveedor_export,
    build_generic_export,
    build_libro_iva_digital,
    build_lista_reposicion,
    build_pagos_export,
    build_resumen_clientes,
    build_resumen_proveedores,
    build_stock_export,
    build_stock_valorizado,
    build_ventas_detallado,
    build_ventas_export,
    make_filename,
)

__all__ = [
    "build_cobranzas_export",
    "build_compras_export",
    "build_cta_cte_cliente_export",
    "build_cta_cte_proveedor_export",
    "build_generic_export",
    "build_libro_iva_digital",
    "build_lista_reposicion",
    "build_pagos_export",
    "build_resumen_clientes",
    "build_resumen_proveedores",
    "build_stock_export",
    "build_stock_valorizado",
    "build_ventas_detallado",
    "build_ventas_export",
    "make_filename",
]
