"""Detector: facturas con mismo total al mismo proveedor casi idénticas.

Heurística más estricta que pago_duplicado: agrupa por (proveedor, total) en
movimientos de pago a proveedor; si hay >=2 con total exacto, emite alerta
de severidad alta.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.models.alerta import SeveridadEnum, TipoAlertaEnum
from app.models.resumen import MovimientoCaja, TipoMovimientoEnum

from .. import Detector, hash_payload


class FacturaCompraRepetidaDetector(Detector):
    tipo = TipoAlertaEnum.factura_compra_repetida

    def detect(self, session, ventana_dias: int = 90) -> list[dict[str, Any]]:
        """Detecta facturas de compra (pagos a proveedor) con mismo total exacto.

        Más estricto que pago_duplicado:
        - mismo proveedor
        - mismo total exacto (al centavo)
        - en ventana de 7 días
        - sin agrupar por pares — toda la canasta entra en una sola alerta
        """
        desde = datetime.now(timezone.utc) - timedelta(days=ventana_dias)
        rows = (
            session.execute(
                select(MovimientoCaja)
                .where(MovimientoCaja.tipo == TipoMovimientoEnum.pago_proveedor)
                .where(MovimientoCaja.fecha >= desde)
                .where(MovimientoCaja.proveedor_id.is_not(None))
            )
            .scalars()
            .all()
        )

        buckets: dict[tuple[int, Decimal], list[MovimientoCaja]] = defaultdict(list)
        for m in rows:
            key = (int(m.proveedor_id), abs(m.monto).quantize(Decimal("0.01")))
            buckets[key].append(m)

        candidatos: list[dict[str, Any]] = []
        for (prov_id, monto), movs in buckets.items():
            if len(movs) < 2:
                continue
            movs.sort(key=lambda x: x.fecha)

            cluster: list[MovimientoCaja] = [movs[0]]
            for m in movs[1:]:
                if (m.fecha - cluster[-1].fecha).days <= 7:
                    cluster.append(m)
                else:
                    if len(cluster) >= 2:
                        candidatos.append(self._build(prov_id, monto, cluster))
                    cluster = [m]
            if len(cluster) >= 2:
                candidatos.append(self._build(prov_id, monto, cluster))

        return candidatos

    @staticmethod
    def _build(prov_id: int, monto: Decimal, cluster: list[MovimientoCaja]) -> dict[str, Any]:
        ids = sorted([m.id for m in cluster])
        h = hash_payload("factura_compra_repetida", prov_id, monto, *ids)
        return {
            "tipo": TipoAlertaEnum.factura_compra_repetida,
            "severidad": SeveridadEnum.alta,
            "titulo": (
                f"{len(cluster)} facturas de compra repetidas al proveedor #{prov_id}"
            ),
            "descripcion": (
                f"Se detectaron {len(cluster)} pagos por exactamente "
                f"${monto} al proveedor #{prov_id} en menos de 7 días. "
                f"Probable factura repetida — revisar antes de pagar."
            ),
            "contexto": {
                "proveedor_id": prov_id,
                "monto": str(monto),
                "movimiento_ids": ids,
                "fechas": [m.fecha.isoformat() for m in cluster],
                "factura_ids": [m.factura_id for m in cluster if m.factura_id],
            },
            "proveedor_id": prov_id,
            "factura_id": cluster[0].factura_id,
            "deteccion_hash": h,
        }
