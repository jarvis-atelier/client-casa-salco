"""Detector: rotación lenta — artículo con velocidad < 0.1/día sostenida en
últimos 60 días Y stock por encima del mínimo (no es un agotamiento).

Sugiere reducir el mínimo o lanzar promo. Severidad baja.
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


VELOCIDAD_LENTA_UMBRAL = Decimal("0.1")  # unidades/día
VENTANA_DIAS = 60


class RotacionLentaDetector(Detector):
    tipo = TipoAlertaEnum.rotacion_lenta

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
            if cantidad <= 0:
                continue
            efectivo_min = row.efectivo_minimo or Decimal("0")
            # Solo consideramos rotación lenta cuando NO está bajo mínimo
            if cantidad <= efectivo_min:
                continue

            velocidad = calcular_velocidad_venta(
                session,
                articulo.id,
                row.sucursal_id,
                dias=VENTANA_DIAS,
            )
            v_diaria = Decimal(str(velocidad["velocidad_promedio_diaria"]))
            if v_diaria >= VELOCIDAD_LENTA_UMBRAL:
                continue
            # Si nunca se vendió, no levantamos alerta — puede ser un alta
            # reciente. Se requiere al menos 1 día con venta en la ventana.
            if velocidad["dias_con_venta"] == 0:
                continue

            h = hash_payload(
                "rotacion_lenta",
                articulo.id,
                row.sucursal_id,
                hoy_iso,
            )

            sucursal_nombre = (
                row.sucursal.nombre if row.sucursal else f"#{row.sucursal_id}"
            )
            candidatos.append(
                {
                    "tipo": TipoAlertaEnum.rotacion_lenta,
                    "severidad": SeveridadEnum.baja,
                    "titulo": (
                        f"Rotación lenta: {articulo.codigo} en {sucursal_nombre}"
                    ),
                    "descripcion": (
                        f"El artículo {articulo.codigo} ({articulo.descripcion}) "
                        f"vende {v_diaria}/día en {sucursal_nombre} (ventana "
                        f"{VENTANA_DIAS}d, umbral {VELOCIDAD_LENTA_UMBRAL}). "
                        f"Stock actual: {cantidad}. Considerar reducir mínimo o promocionar."
                    ),
                    "contexto": {
                        "articulo_id": articulo.id,
                        "articulo_codigo": articulo.codigo,
                        "sucursal_id": row.sucursal_id,
                        "cantidad_actual": str(cantidad),
                        "velocidad_diaria": str(v_diaria),
                        "dias_con_venta": velocidad["dias_con_venta"],
                        "ventana_dias": VENTANA_DIAS,
                        "fecha": hoy_iso,
                    },
                    "sucursal_id": row.sucursal_id,
                    "deteccion_hash": h,
                }
            )

        return candidatos
