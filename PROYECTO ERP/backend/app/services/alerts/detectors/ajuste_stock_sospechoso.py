"""Detector: ajustes manuales de stock negativos sin venta correlacionada.

Busca movimientos `ajuste` (TipoMovimientoEnum.ajuste) con monto negativo
que NO se correlacionan con una venta o devolución registrada en el mismo
día y sucursal por monto similar.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.models.alerta import SeveridadEnum, TipoAlertaEnum
from app.models.resumen import MovimientoCaja, TipoMovimientoEnum

from .. import Detector, hash_payload


class AjusteStockSospechosoDetector(Detector):
    tipo = TipoAlertaEnum.ajuste_stock_sospechoso

    def detect(self, session, ventana_dias: int = 90) -> list[dict[str, Any]]:
        desde = datetime.now(timezone.utc) - timedelta(days=ventana_dias)

        ajustes = (
            session.execute(
                select(MovimientoCaja)
                .where(MovimientoCaja.tipo == TipoMovimientoEnum.ajuste)
                .where(MovimientoCaja.fecha >= desde)
                .where(MovimientoCaja.monto < 0)
            )
            .scalars()
            .all()
        )

        if not ajustes:
            return []

        # Pre-cache de ventas/devoluciones por (sucursal, fecha_caja)
        ventas = (
            session.execute(
                select(MovimientoCaja)
                .where(
                    MovimientoCaja.tipo.in_(
                        [
                            TipoMovimientoEnum.venta,
                            TipoMovimientoEnum.devolucion,
                        ]
                    )
                )
                .where(MovimientoCaja.fecha >= desde)
            )
            .scalars()
            .all()
        )

        ventas_idx: dict[tuple[int, str], list[Decimal]] = {}
        for v in ventas:
            k = (v.sucursal_id, v.fecha_caja.isoformat())
            ventas_idx.setdefault(k, []).append(abs(v.monto))

        candidatos: list[dict[str, Any]] = []
        for aj in ajustes:
            monto_aj = abs(aj.monto)
            key = (aj.sucursal_id, aj.fecha_caja.isoformat())
            ventas_dia = ventas_idx.get(key, [])

            # Hay venta del día con monto similar (±5%)?
            tolerancia = monto_aj * Decimal("0.05")
            correlaciona = any(
                abs(v - monto_aj) <= tolerancia for v in ventas_dia
            )
            if correlaciona:
                continue

            severidad = (
                SeveridadEnum.alta
                if monto_aj > Decimal("50000")
                else SeveridadEnum.media
            )

            h = hash_payload(
                "ajuste_stock_sospechoso",
                aj.id,
                aj.sucursal_id,
                monto_aj,
                aj.fecha_caja.isoformat(),
            )
            candidatos.append(
                {
                    "tipo": TipoAlertaEnum.ajuste_stock_sospechoso,
                    "severidad": severidad,
                    "titulo": (
                        f"Ajuste manual sin venta correlacionada "
                        f"(${monto_aj})"
                    ),
                    "descripcion": (
                        f"Se registró un ajuste manual negativo de ${monto_aj} "
                        f"en sucursal #{aj.sucursal_id} el "
                        f"{aj.fecha_caja.isoformat()} sin que haya una venta "
                        f"o devolución del día por monto similar. "
                        f"Posible faltante no justificado."
                    ),
                    "contexto": {
                        "movimiento_id": aj.id,
                        "sucursal_id": aj.sucursal_id,
                        "monto": str(monto_aj),
                        "fecha_caja": aj.fecha_caja.isoformat(),
                        "user_id": aj.user_id,
                        "descripcion_movimiento": aj.descripcion,
                    },
                    "sucursal_id": aj.sucursal_id,
                    "user_relacionado_id": aj.user_id,
                    "deteccion_hash": h,
                }
            )

        return candidatos
