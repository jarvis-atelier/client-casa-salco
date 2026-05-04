"""Detector: items de venta repetidos en facturas distintas, mismo cajero, ventana corta.

Indicador típico de cajero "duplicando líneas" — misma descripción + cantidad +
precio en facturas distintas del mismo cajero en menos de 30 minutos.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.models.alerta import SeveridadEnum, TipoAlertaEnum
from app.models.factura import EstadoComprobanteEnum, Factura
from app.models.factura_item import FacturaItem

from .. import Detector, hash_payload


class ItemsRepetidosDiffNroDetector(Detector):
    tipo = TipoAlertaEnum.items_repetidos_diff_nro

    def detect(self, session, ventana_dias: int = 90) -> list[dict[str, Any]]:
        """Items idénticos en facturas distintas del mismo cajero, < 30 min.

        Patrón sospechoso: cajero emite la misma "línea" (mismo articulo +
        cantidad + precio) en facturas diferentes en una ventana muy corta.
        """
        desde = datetime.now(timezone.utc) - timedelta(days=ventana_dias)

        rows = session.execute(
            select(
                FacturaItem.id,
                FacturaItem.factura_id,
                FacturaItem.articulo_id,
                FacturaItem.cantidad,
                FacturaItem.precio_unitario,
                FacturaItem.descripcion,
                Factura.cajero_id,
                Factura.fecha,
                Factura.sucursal_id,
                Factura.numero,
            )
            .join(Factura, Factura.id == FacturaItem.factura_id)
            .where(Factura.fecha >= desde)
            .where(Factura.estado == EstadoComprobanteEnum.emitida)
        ).all()

        # Agrupar por (cajero, articulo, cantidad, precio)
        buckets: dict[tuple, list[Any]] = defaultdict(list)
        for r in rows:
            key = (
                r.cajero_id,
                r.articulo_id,
                Decimal(r.cantidad).quantize(Decimal("0.0001")),
                Decimal(r.precio_unitario).quantize(Decimal("0.0001")),
            )
            buckets[key].append(r)

        candidatos: list[dict[str, Any]] = []
        for key, items in buckets.items():
            if len(items) < 2:
                continue
            cajero_id, art_id, cant, precio = key
            # Solo cuenta si vienen de facturas distintas
            facturas_distintas = {it.factura_id for it in items}
            if len(facturas_distintas) < 2:
                continue
            items.sort(key=lambda x: x.fecha)
            for i in range(len(items) - 1):
                a = items[i]
                b = items[i + 1]
                if a.factura_id == b.factura_id:
                    continue
                delta_min = abs((b.fecha - a.fecha).total_seconds()) / 60
                if delta_min > 30:
                    continue

                h = hash_payload(
                    "items_repetidos",
                    cajero_id,
                    art_id,
                    cant,
                    precio,
                    min(a.id, b.id),
                    max(a.id, b.id),
                )
                candidatos.append(
                    {
                        "tipo": TipoAlertaEnum.items_repetidos_diff_nro,
                        "severidad": SeveridadEnum.media,
                        "titulo": (
                            f"Item repetido en facturas distintas "
                            f"(cajero #{cajero_id})"
                        ),
                        "descripcion": (
                            f"El cajero #{cajero_id} cargó el artículo "
                            f"#{art_id} con cantidad {cant} y precio "
                            f"${precio} en dos facturas distintas separadas "
                            f"por {delta_min:.0f} minutos."
                        ),
                        "contexto": {
                            "cajero_id": cajero_id,
                            "articulo_id": art_id,
                            "cantidad": str(cant),
                            "precio_unitario": str(precio),
                            "factura_ids": [a.factura_id, b.factura_id],
                            "delta_minutos": round(delta_min, 1),
                            "descripcion_item": a.descripcion,
                        },
                        "factura_id": a.factura_id,
                        "user_relacionado_id": cajero_id,
                        "sucursal_id": a.sucursal_id,
                        "deteccion_hash": h,
                    }
                )

        return candidatos
