"""Mappers ETL: un modulo por entidad destino.

Cada mapper expone:
    extract(source_dir: Path, encoding: str) -> Iterator[dict]
    load(session, rows: Iterable[dict], dry_run: bool = False) -> LoadReport

Orden tipico de importacion (respetando FKs):
    1. proveedores
    2. familias_rubros   (crea "Sin familia" / "Sin rubro" fallback)
    3. clientes
    4. articulos         (depende de familias, rubros, proveedores)
    5. articulos_proveedores (depende de articulos + proveedores)
"""
from .common import LoadReport, WarningRecord, clean_str, decimal_or_zero, sanitize_text

__all__ = [
    "LoadReport",
    "WarningRecord",
    "clean_str",
    "decimal_or_zero",
    "sanitize_text",
]
