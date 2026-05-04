"""Detector: compromisos de pago próximos a vencer o ya vencidos.

Levanta una alerta por cada `CompromisoPago` en estado `pendiente` o `parcial`
que esté:
- Vencido (severidad crítica).
- Vence hoy (severidad alta).
- Vence en 1 a 3 días (severidad media).
- Vence en 4 a 7 días (severidad baja).

El hash incluye el `id` del compromiso, su fecha de vencimiento y su estado,
así que si la fecha de vencimiento se reagenda o cambia el estado se emite
una alerta nueva (es lo que queremos: la situación cambió).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import select

from app.models.alerta import SeveridadEnum, TipoAlertaEnum
from app.models.calendario_pago import CompromisoPago, EstadoCompromisoEnum

from .. import Detector, hash_payload


class VencimientoProximoDetector(Detector):
    tipo = TipoAlertaEnum.vencimiento_proximo

    def detect(self, session, ventana_dias: int = 30) -> list[dict[str, Any]]:
        """Detecta compromisos próximos a vencer.

        `ventana_dias` se usa para limitar cuán atrás miramos vencimientos
        atrasados (por defecto, los últimos 30 días).
        """
        hoy = date.today()
        limite_futuro = hoy + timedelta(days=7)
        limite_pasado = hoy - timedelta(days=min(ventana_dias, 30))

        rows = (
            session.execute(
                select(CompromisoPago)
                .where(
                    CompromisoPago.estado.in_(
                        [
                            EstadoCompromisoEnum.pendiente,
                            EstadoCompromisoEnum.parcial,
                            EstadoCompromisoEnum.vencido,
                        ]
                    )
                )
                .where(CompromisoPago.fecha_vencimiento >= limite_pasado)
                .where(CompromisoPago.fecha_vencimiento <= limite_futuro)
            )
            .scalars()
            .all()
        )

        candidatos: list[dict[str, Any]] = []
        for c in rows:
            dias = (c.fecha_vencimiento - hoy).days
            pendiente = c.monto_pendiente
            if pendiente <= 0:
                # Si ya está pagado por completo, no alertamos.
                continue

            if dias < 0:
                severidad = SeveridadEnum.critica
                titulo = f"VENCIDO hace {-dias} día(s): {c.descripcion}"
            elif dias == 0:
                severidad = SeveridadEnum.alta
                titulo = f"Vence HOY: {c.descripcion}"
            elif dias <= 3:
                severidad = SeveridadEnum.media
                titulo = f"Vence en {dias} día(s): {c.descripcion}"
            else:
                severidad = SeveridadEnum.baja
                titulo = f"Vence en {dias} día(s): {c.descripcion}"

            h = hash_payload(
                "vencimiento_proximo",
                c.id,
                c.fecha_vencimiento.isoformat(),
                c.estado.value,
            )
            descripcion = (
                f"Compromiso {c.tipo.value} — pendiente ${pendiente} — "
                f"vence {c.fecha_vencimiento.isoformat()}."
            )
            candidatos.append(
                {
                    "tipo": self.tipo,
                    "severidad": severidad,
                    "titulo": titulo[:200],
                    "descripcion": descripcion,
                    "contexto": {
                        "compromiso_id": c.id,
                        "tipo_compromiso": c.tipo.value,
                        "estado": c.estado.value,
                        "dias": dias,
                        "monto_pendiente": str(pendiente),
                        "fecha_vencimiento": c.fecha_vencimiento.isoformat(),
                    },
                    "proveedor_id": c.proveedor_id,
                    "factura_id": c.factura_id,
                    "sucursal_id": c.sucursal_id,
                    "deteccion_hash": h,
                }
            )

        return candidatos
