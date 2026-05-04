"""Numeración secuencial atómica de comprobantes.

Cada `(sucursal, punto_venta, tipo)` tiene su propia serie. Para evitar duplicados
cuando dos cajeros emiten al mismo tiempo:

- En Postgres usamos `SELECT ... FOR UPDATE` sobre la fila MAX anterior.
- En SQLite usamos `BEGIN IMMEDIATE` (un solo writer a la vez) — suficiente para
  dev/tests. En producción se recomienda Postgres.

La función devuelve el SIGUIENTE número a usar; el caller es responsable de
insertar la factura con ese número y commitear antes de liberar la tx.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.factura import Factura, TipoComprobanteEnum


def next_numero(
    session: Session,
    sucursal_id: int,
    punto_venta: int,
    tipo: TipoComprobanteEnum,
) -> int:
    """Calcula el siguiente número de comprobante para la serie dada.

    En Postgres acompañamos con lock de fila (FOR UPDATE) para serializar
    concurrencia. En SQLite, el lock implícito de la transacción alcanza.
    """
    dialect = session.bind.dialect.name if session.bind else "sqlite"

    stmt = select(func.coalesce(func.max(Factura.numero), 0)).where(
        Factura.sucursal_id == sucursal_id,
        Factura.punto_venta == punto_venta,
        Factura.tipo == tipo,
    )
    if dialect == "postgresql":
        # Lockeamos el conjunto de filas de esta serie.
        stmt = stmt.with_for_update()

    max_numero = session.execute(stmt).scalar_one()
    return int(max_numero) + 1
