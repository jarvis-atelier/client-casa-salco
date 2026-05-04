"""Helpers compartidos entre mappers.

- LoadReport: estructura uniforme de reporte por mapper.
- Funciones de sanitizacion (clean_str, decimal_or_zero).
- Mapeos de enums legacy -> enums del modelo nuevo.
"""
from __future__ import annotations

import time
import unicodedata
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

# Enums del modelo destino
from app.models.articulo import UnidadMedidaEnum
from app.models.cliente import CondicionIvaEnum


@dataclass
class WarningRecord:
    """Fila que se saltó o ajustó con una razón legible."""

    entity: str
    identifier: str
    reason: str

    def __str__(self) -> str:
        return f"[{self.entity}] {self.identifier}: {self.reason}"


@dataclass
class LoadReport:
    """Resultado de correr load() para un mapper."""

    entity: str
    read: int = 0
    inserted: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0
    warnings: list[WarningRecord] = field(default_factory=list)
    elapsed_s: float = 0.0

    _started_at: float | None = None

    def start(self) -> None:
        self._started_at = time.perf_counter()

    def finish(self) -> None:
        if self._started_at is not None:
            self.elapsed_s = time.perf_counter() - self._started_at

    def warn(self, identifier: str, reason: str) -> None:
        self.warnings.append(WarningRecord(self.entity, identifier, reason))

    def as_summary_row(self) -> tuple[str, int, int, int, int, int, float]:
        return (
            self.entity,
            self.read,
            self.inserted,
            self.updated,
            self.skipped,
            self.failed,
            round(self.elapsed_s, 2),
        )


# ---------------------------------------------------------------------------
# Sanitizacion
# ---------------------------------------------------------------------------

def clean_str(value: Any, max_len: int | None = None) -> str | None:
    """Normaliza strings venidos del DBF: strip, colapsa espacios, None si vacio.

    - Reemplaza caracteres de reemplazo (chr(0xFFFD)) por '?'.
    - Elimina NULL bytes que a veces quedan en xBase.
    - Opcionalmente trunca a max_len.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    # NULL bytes y control chars basicos
    value = value.replace("\x00", "").replace("\r", " ").replace("\n", " ")
    value = " ".join(value.split())  # colapsa espacios
    if not value:
        return None
    if max_len and len(value) > max_len:
        value = value[:max_len]
    return value


def sanitize_text(value: Any, max_len: int | None = None) -> str | None:
    """Sanitiza y normaliza Unicode; reemplaza chars no imprimibles."""
    s = clean_str(value, max_len=max_len)
    if s is None:
        return None
    # Normaliza (NFC) - no quita acentos
    try:
        s = unicodedata.normalize("NFC", s)
    except Exception:
        pass
    return s


def decimal_or_zero(value: Any, places: int = 4) -> Decimal:
    """Convierte a Decimal preservando precision. Float -> str para evitar drift."""
    if value is None or value == "":
        return Decimal("0")
    try:
        if isinstance(value, Decimal):
            return value
        # Float -> str para no arrastrar ruido de binario
        return Decimal(str(value)).quantize(Decimal(10) ** -places)
    except (InvalidOperation, ValueError):
        return Decimal("0")


def int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def bool_from_legacy(value: Any) -> bool:
    """Legacy usa L (bool), N 1/0, o C 'S'/'N'."""
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value != 0
    if isinstance(value, str):
        return value.strip().upper() in ("S", "SI", "Y", "YES", "1", "T", "TRUE")
    return False


# ---------------------------------------------------------------------------
# Mapeos de enums legacy -> destino
# ---------------------------------------------------------------------------

# Legacy CLIENTES.NUIV / PROVEEDO.NUIV (1..7):
# 1=CONSUMIDOR FINAL, 2=MONOTRIBUTO, 3=RI, 4=NO ALCANZADO,
# 5=EXENTO, 6=NO RESPONSABLE, 7=NO CATEGORIZADO
NUIV_TO_CONDICION_IVA: dict[int, CondicionIvaEnum] = {
    1: CondicionIvaEnum.consumidor_final,
    2: CondicionIvaEnum.monotributo,
    3: CondicionIvaEnum.responsable_inscripto,
    4: CondicionIvaEnum.no_categorizado,   # no alcanzado - el modelo no lo tiene
    5: CondicionIvaEnum.exento,
    6: CondicionIvaEnum.no_categorizado,   # no responsable
    7: CondicionIvaEnum.no_categorizado,
}

# Legacy ARTICULO.UNID ('S'/'N') y parame->serv6[3] determinan kg vs unidad.
# El modelo nuevo usa UnidadMedidaEnum: unidad / kg / gr / lt / ml.
# Sin pistas textuales confiables en el DBF base, usamos UNID=S -> kg (pesable),
# UNID=N o vacio -> unidad.

def unidad_medida_from_legacy(unid: Any, desc: str | None = None) -> UnidadMedidaEnum:
    """Decide unidad de medida a partir del flag UNID y heuristicas de la descripcion."""
    if isinstance(unid, str) and unid.strip().upper() == "S":
        return UnidadMedidaEnum.kg
    d = (desc or "").lower()
    # heuristicas defensivas
    if any(kw in d for kw in (" kg", "kilo", "kgs")):
        return UnidadMedidaEnum.kg
    if any(kw in d for kw in (" lt", " litro", "litros")):
        return UnidadMedidaEnum.lt
    if any(kw in d for kw in (" ml ", " mililitro")):
        return UnidadMedidaEnum.ml
    if any(kw in d for kw in (" gr ", " gramo", " grs ")):
        return UnidadMedidaEnum.gr
    return UnidadMedidaEnum.unidad
