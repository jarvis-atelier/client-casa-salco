"""Runner de detectores: corre todos y persiste alertas nuevas (idempotente)."""
from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models.alerta import Alerta

from .detectors import (
    AjusteStockSospechosoDetector,
    AnulacionesFrecuentesDetector,
    FacturaCompraRepetidaDetector,
    ItemsRepetidosDiffNroDetector,
    PagoDuplicadoDetector,
    RotacionLentaDetector,
    RotacionRapidaFaltanteDetector,
    SobrestockDetector,
    StockBajoMinimoDetector,
    VencimientoProximoDetector,
)


def get_all_detectors():
    """Lista de instancias de detectores en orden de severidad típica."""
    return [
        PagoDuplicadoDetector(),
        FacturaCompraRepetidaDetector(),
        ItemsRepetidosDiffNroDetector(),
        AnulacionesFrecuentesDetector(),
        AjusteStockSospechosoDetector(),
        VencimientoProximoDetector(),
        # Stock inteligente — opción C
        StockBajoMinimoDetector(),
        SobrestockDetector(),
        RotacionRapidaFaltanteDetector(),
        RotacionLentaDetector(),
    ]


def run_all_detectors(session, ventana_dias: int = 90) -> dict[str, Any]:
    """Corre todos los detectores y crea las alertas nuevas.

    Retorna `{creadas, detectores, detalle: {tipo: count}}`.

    Idempotente: si una alerta con el mismo `deteccion_hash` ya existe en
    cualquier estado (incluso descartada), no la vuelve a crear.
    """
    detectores = get_all_detectors()
    creadas_total = 0
    detalle: dict[str, int] = {}

    # Cargar todos los hashes existentes una vez (más rápido que N consultas)
    existing_hashes = {
        h for (h,) in session.execute(select(Alerta.deteccion_hash)).all()
    }

    for det in detectores:
        creadas_det = 0
        candidatos = det.detect(session, ventana_dias=ventana_dias)
        for c in candidatos:
            h = c["deteccion_hash"]
            if h in existing_hashes:
                continue
            session.add(Alerta(**c))
            existing_hashes.add(h)
            creadas_det += 1
        detalle[det.tipo.value] = creadas_det
        creadas_total += creadas_det

    session.commit()
    return {
        "creadas": creadas_total,
        "detectores": len(detectores),
        "detalle": detalle,
    }
