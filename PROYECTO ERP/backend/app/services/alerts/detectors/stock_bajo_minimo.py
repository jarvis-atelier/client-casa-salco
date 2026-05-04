"""Detector: stock bajo el mínimo efectivo (sucursal o default articulo).

Severidad alta cuando cantidad <= efectivo_minimo. El hash incluye la fecha
del día (no la hora) para que la alerta no se duplique mientras siga el
problema dentro del mismo día — pero sí se vuelva a generar al día siguiente
si el problema persiste.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from app.models.alerta import SeveridadEnum, TipoAlertaEnum
from app.models.articulo import Articulo
from app.models.stock import StockSucursal

from .. import Detector, hash_payload


class StockBajoMinimoDetector(Detector):
    tipo = TipoAlertaEnum.stock_bajo_minimo

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
            efectivo_min = row.efectivo_minimo
            if efectivo_min is None:
                continue
            cantidad = row.cantidad or Decimal("0")
            if cantidad > efectivo_min:
                continue

            severidad = (
                SeveridadEnum.critica
                if cantidad <= 0
                else SeveridadEnum.alta
            )
            estado = row.estado_reposicion

            h = hash_payload(
                "stock_bajo_minimo",
                articulo.id,
                row.sucursal_id,
                hoy_iso,
            )

            sucursal_nombre = (
                row.sucursal.nombre if row.sucursal else f"#{row.sucursal_id}"
            )
            candidatos.append(
                {
                    "tipo": TipoAlertaEnum.stock_bajo_minimo,
                    "severidad": severidad,
                    "titulo": (
                        f"Stock bajo mínimo: {articulo.codigo} "
                        f"({cantidad}/{efectivo_min}) — {sucursal_nombre}"
                    ),
                    "descripcion": (
                        f"El artículo {articulo.codigo} ({articulo.descripcion}) "
                        f"en {sucursal_nombre} tiene {cantidad} unidades, "
                        f"por debajo del mínimo configurado ({efectivo_min}). "
                        f"Estado: {estado}."
                    ),
                    "contexto": {
                        "articulo_id": articulo.id,
                        "articulo_codigo": articulo.codigo,
                        "sucursal_id": row.sucursal_id,
                        "cantidad_actual": str(cantidad),
                        "stock_minimo": str(efectivo_min),
                        "estado": estado,
                        "fecha": hoy_iso,
                    },
                    "sucursal_id": row.sucursal_id,
                    "deteccion_hash": h,
                }
            )

        return candidatos
