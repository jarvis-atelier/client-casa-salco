"""Detector: rotación rápida con quiebres de stock — el artículo se quedó en 0
varias veces en últimos 30 días. Sugiere SUBIR el efectivo_minimo.

Heurística (proxy mientras no haya historial diario de stock):
- velocidad de venta >= 1.0 / día en últimos 30 días
- cantidad actual = 0  (está agotado AHORA)

Severidad media. La alerta se levanta una vez por día.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.alerta import SeveridadEnum, TipoAlertaEnum
from app.models.stock import StockSucursal
from app.services.analytics.velocidad_venta import calcular_velocidad_venta

from .. import Detector, hash_payload


VELOCIDAD_RAPIDA_UMBRAL = Decimal("1.0")  # unidades/día
VENTANA_DIAS = 30


class RotacionRapidaFaltanteDetector(Detector):
    tipo = TipoAlertaEnum.rotacion_rapida_faltante

    def detect(self, session, ventana_dias: int = 90) -> list[dict[str, Any]]:
        rows = (
            session.execute(
                select(StockSucursal).options(
                    joinedload(StockSucursal.articulo),
                    joinedload(StockSucursal.sucursal),
                )
            )
            .scalars()
            .unique()
            .all()
        )

        candidatos: list[dict[str, Any]] = []
        hoy_iso = date.today().isoformat()

        for row in rows:
            articulo = row.articulo
            if articulo is None or not articulo.activo or not articulo.controla_stock:
                continue
            cantidad = row.cantidad or Decimal("0")
            # Sólo cuando está agotado AHORA
            if cantidad > 0:
                continue

            velocidad = calcular_velocidad_venta(
                session,
                articulo.id,
                row.sucursal_id,
                dias=VENTANA_DIAS,
            )
            v_diaria = Decimal(str(velocidad["velocidad_promedio_diaria"]))
            if v_diaria < VELOCIDAD_RAPIDA_UMBRAL:
                continue

            efectivo_min = row.efectivo_minimo or Decimal("0")
            sugerido_min = (v_diaria * Decimal("3")).quantize(Decimal("1"))

            h = hash_payload(
                "rotacion_rapida_faltante",
                articulo.id,
                row.sucursal_id,
                hoy_iso,
            )

            sucursal_nombre = (
                row.sucursal.nombre if row.sucursal else f"#{row.sucursal_id}"
            )
            candidatos.append(
                {
                    "tipo": TipoAlertaEnum.rotacion_rapida_faltante,
                    "severidad": SeveridadEnum.media,
                    "titulo": (
                        f"Quiebre de stock: {articulo.codigo} en {sucursal_nombre}"
                    ),
                    "descripcion": (
                        f"{articulo.codigo} ({articulo.descripcion}) está en 0 en "
                        f"{sucursal_nombre} pero rota rápido ({v_diaria}/día). "
                        f"Mínimo actual: {efectivo_min}. Sugerido: {sugerido_min}."
                    ),
                    "contexto": {
                        "articulo_id": articulo.id,
                        "articulo_codigo": articulo.codigo,
                        "sucursal_id": row.sucursal_id,
                        "velocidad_diaria": str(v_diaria),
                        "stock_minimo_actual": str(efectivo_min),
                        "stock_minimo_sugerido": str(sugerido_min),
                        "ventana_dias": VENTANA_DIAS,
                        "fecha": hoy_iso,
                    },
                    "sucursal_id": row.sucursal_id,
                    "deteccion_hash": h,
                }
            )

        return candidatos
