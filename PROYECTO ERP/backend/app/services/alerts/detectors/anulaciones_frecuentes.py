"""Detector: cajero con tasa de anulaciones alta en últimos 30 días.

Heurísticas:
- Si un cajero anuló > 5% de sus ventas en los últimos 30 días → alerta media.
- Si un cajero tuvo > 3 anulaciones en una misma jornada → alerta alta.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select

from app.models.alerta import SeveridadEnum, TipoAlertaEnum
from app.models.factura import EstadoComprobanteEnum, Factura

from .. import Detector, hash_payload


class AnulacionesFrecuentesDetector(Detector):
    tipo = TipoAlertaEnum.anulaciones_frecuentes

    def detect(self, session, ventana_dias: int = 90) -> list[dict[str, Any]]:
        # Para tasas, usamos los últimos 30 días aunque la ventana global sea mayor.
        ventana = min(ventana_dias, 30)
        desde = datetime.now(timezone.utc) - timedelta(days=ventana)

        rows = (
            session.execute(
                select(Factura).where(Factura.fecha >= desde)
            )
            .scalars()
            .all()
        )

        # Por cajero: total facturas y anuladas
        por_cajero_total: dict[int, int] = defaultdict(int)
        por_cajero_anu: dict[int, int] = defaultdict(int)

        # Por (cajero, fecha_caja): anulaciones del día
        por_cajero_dia: dict[tuple[int, str], list[int]] = defaultdict(list)

        for f in rows:
            cajero_id = f.cajero_id
            por_cajero_total[cajero_id] += 1
            if f.estado == EstadoComprobanteEnum.anulada:
                por_cajero_anu[cajero_id] += 1
                fecha_str = f.fecha.date().isoformat()
                por_cajero_dia[(cajero_id, fecha_str)].append(f.id)

        candidatos: list[dict[str, Any]] = []

        for cajero_id, total in por_cajero_total.items():
            anuladas = por_cajero_anu.get(cajero_id, 0)
            if total >= 20 and anuladas / total > 0.05:
                pct = anuladas / total * 100
                h = hash_payload(
                    "anulaciones_frecuentes_pct",
                    cajero_id,
                    desde.date().isoformat(),
                    anuladas,
                    total,
                )
                candidatos.append(
                    {
                        "tipo": TipoAlertaEnum.anulaciones_frecuentes,
                        "severidad": SeveridadEnum.media,
                        "titulo": (
                            f"Cajero #{cajero_id}: {pct:.1f}% de anulaciones"
                        ),
                        "descripcion": (
                            f"En los últimos {ventana} días el cajero "
                            f"#{cajero_id} tuvo {anuladas} anulaciones de "
                            f"{total} facturas ({pct:.1f}%, umbral 5%)."
                        ),
                        "contexto": {
                            "cajero_id": cajero_id,
                            "total_facturas": total,
                            "anuladas": anuladas,
                            "porcentaje": round(pct, 2),
                            "ventana_dias": ventana,
                        },
                        "user_relacionado_id": cajero_id,
                        "deteccion_hash": h,
                    }
                )

        for (cajero_id, fecha_str), ids in por_cajero_dia.items():
            if len(ids) > 3:
                h = hash_payload(
                    "anulaciones_frecuentes_dia",
                    cajero_id,
                    fecha_str,
                    len(ids),
                )
                candidatos.append(
                    {
                        "tipo": TipoAlertaEnum.anulaciones_frecuentes,
                        "severidad": SeveridadEnum.alta,
                        "titulo": (
                            f"Cajero #{cajero_id}: {len(ids)} anulaciones "
                            f"el {fecha_str}"
                        ),
                        "descripcion": (
                            f"El cajero #{cajero_id} anuló {len(ids)} "
                            f"facturas el {fecha_str}. Más de 3 anulaciones "
                            f"en un día es inusual."
                        ),
                        "contexto": {
                            "cajero_id": cajero_id,
                            "fecha": fecha_str,
                            "factura_ids": ids,
                            "cantidad": len(ids),
                        },
                        "user_relacionado_id": cajero_id,
                        "factura_id": ids[0] if ids else None,
                        "deteccion_hash": h,
                    }
                )

        return candidatos
