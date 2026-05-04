"""Servicios de detección de inconsistencias.

Cada Detector implementa `detect(session, ventana_dias)` y retorna una lista
de candidatos a alerta (dicts) con los campos del modelo Alerta más un
`deteccion_hash` determinístico para evitar duplicar la misma alerta en
re-ejecuciones.
"""
from __future__ import annotations

import hashlib
from abc import ABC, abstractmethod
from typing import Any

from app.models.alerta import TipoAlertaEnum


def hash_payload(*parts: Any) -> str:
    """Calcula un sha256 determinístico a partir de las partes."""
    raw = "|".join(str(p) for p in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class Detector(ABC):
    """Base abstracta para detectores de inconsistencias."""

    tipo: TipoAlertaEnum

    @abstractmethod
    def detect(self, session, ventana_dias: int = 90) -> list[dict[str, Any]]:
        """Retorna candidatos a Alerta (dicts).

        Cada dict debe incluir como mínimo:
        - tipo (TipoAlertaEnum)
        - severidad (SeveridadEnum)
        - titulo (str)
        - descripcion (str)
        - contexto (dict)
        - deteccion_hash (str)

        Y opcionalmente: factura_id, user_relacionado_id, proveedor_id, sucursal_id.
        """
        raise NotImplementedError


__all__ = ["Detector", "hash_payload"]
