"""Detector: sobrestock — cantidad por encima del máximo efectivo.

Especialmente importante en perecederos (controla_vencimiento=True): un
sobrestock puede traducirse en mermas. Severidad media en general; alta
cuando es perecedero.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.alerta import SeveridadEnum, TipoAlertaEnum
from app.models.stock import StockSucursal

from .. import Detector, hash_payload


class SobrestockDetector(Detector):
    tipo = TipoAlertaEnum.sobrestock

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
            efectivo_max = row.efectivo_maximo
            if efectivo_max is None or efectivo_max <= 0:
                continue
            cantidad = row.cantidad or Decimal("0")
            if cantidad <= efectivo_max:
                continue

            exceso = cantidad - efectivo_max
            severidad = (
                SeveridadEnum.alta
                if articulo.controla_vencimiento
                else SeveridadEnum.media
            )

            h = hash_payload(
                "sobrestock",
                articulo.id,
                row.sucursal_id,
                hoy_iso,
            )

            sucursal_nombre = (
                row.sucursal.nombre if row.sucursal else f"#{row.sucursal_id}"
            )
            tag_perecedero = " (perecedero)" if articulo.controla_vencimiento else ""
            candidatos.append(
                {
                    "tipo": TipoAlertaEnum.sobrestock,
                    "severidad": severidad,
                    "titulo": (
                        f"Sobrestock{tag_perecedero}: {articulo.codigo} "
                        f"({cantidad}/{efectivo_max}) — {sucursal_nombre}"
                    ),
                    "descripcion": (
                        f"El artículo {articulo.codigo} ({articulo.descripcion}) "
                        f"en {sucursal_nombre} tiene {cantidad} unidades, "
                        f"{exceso} por encima del máximo ({efectivo_max})."
                        + (
                            " Es perecedero — riesgo de merma."
                            if articulo.controla_vencimiento
                            else ""
                        )
                    ),
                    "contexto": {
                        "articulo_id": articulo.id,
                        "articulo_codigo": articulo.codigo,
                        "sucursal_id": row.sucursal_id,
                        "cantidad_actual": str(cantidad),
                        "stock_maximo": str(efectivo_max),
                        "exceso": str(exceso),
                        "controla_vencimiento": articulo.controla_vencimiento,
                        "fecha": hoy_iso,
                    },
                    "sucursal_id": row.sucursal_id,
                    "deteccion_hash": h,
                }
            )

        return candidatos
