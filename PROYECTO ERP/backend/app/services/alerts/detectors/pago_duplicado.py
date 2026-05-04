"""Detector: pagos a proveedor duplicados.

Busca movimientos `pago_proveedor` con mismo proveedor + mismo monto +
fecha distancia <= 3 días. Si encuentra dos o más con esos rasgos casi-idénticos,
emite alerta crítica.
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


class PagoDuplicadoDetector(Detector):
    tipo = TipoAlertaEnum.pago_duplicado

    def detect(self, session, ventana_dias: int = 90) -> list[dict[str, Any]]:
        """Detecta pagos a proveedor con mismo monto en ventana corta.

        Algoritmo:
        - Toma todos los `pago_proveedor` de los últimos `ventana_dias`.
        - Agrupa por (proveedor_id, monto absoluto). Si hay >= 2 movimientos
          y dos cualesquiera están a distancia <= 3 días → alerta.
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

        # Agrupar por (proveedor_id, monto redondeado)
        buckets: dict[tuple[int, Decimal], list[MovimientoCaja]] = defaultdict(list)
        for m in rows:
            key = (int(m.proveedor_id), abs(m.monto).quantize(Decimal("0.01")))
            buckets[key].append(m)

        candidatos: list[dict[str, Any]] = []
        for (prov_id, monto), movs in buckets.items():
            if len(movs) < 2:
                continue
            movs.sort(key=lambda x: x.fecha)
            # Buscar pares cercanos
            for i in range(len(movs) - 1):
                a = movs[i]
                b = movs[i + 1]
                delta = abs((b.fecha - a.fecha).days)
                if delta > 3:
                    continue

                h = hash_payload(
                    "pago_duplicado",
                    prov_id,
                    monto,
                    min(a.id, b.id),
                    max(a.id, b.id),
                )
                contexto = {
                    "proveedor_id": prov_id,
                    "monto": str(monto),
                    "movimiento_ids": [a.id, b.id],
                    "fechas": [a.fecha.isoformat(), b.fecha.isoformat()],
                    "distancia_dias": delta,
                    "factura_ids": [a.factura_id, b.factura_id],
                }
                candidatos.append(
                    {
                        "tipo": TipoAlertaEnum.pago_duplicado,
                        "severidad": SeveridadEnum.critica,
                        "titulo": f"Pago duplicado a proveedor #{prov_id}",
                        "descripcion": (
                            f"Se detectaron 2 pagos al mismo proveedor por "
                            f"${monto} con sólo {delta} días de diferencia. "
                            f"Verificá si es un pago duplicado."
                        ),
                        "contexto": contexto,
                        "proveedor_id": prov_id,
                        "factura_id": a.factura_id or b.factura_id,
                        "deteccion_hash": h,
                    }
                )

        return candidatos
