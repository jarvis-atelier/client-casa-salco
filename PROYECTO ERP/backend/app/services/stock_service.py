"""Servicio de stock por sucursal — get/adjust/decrement/increment."""
from __future__ import annotations

from decimal import Decimal
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.stock import StockSucursal


def get_or_create(
    session: Session, articulo_id: int, sucursal_id: int
) -> StockSucursal:
    """Devuelve la fila de stock o la crea en 0 si no existe."""
    row = session.execute(
        select(StockSucursal).where(
            StockSucursal.articulo_id == articulo_id,
            StockSucursal.sucursal_id == sucursal_id,
        )
    ).scalar_one_or_none()
    if row is None:
        row = StockSucursal(
            articulo_id=articulo_id,
            sucursal_id=sucursal_id,
            cantidad=Decimal("0"),
        )
        session.add(row)
        session.flush()
    return row


def get_by_articulo(
    session: Session, articulo_id: int
) -> list[StockSucursal]:
    """Stock de un artículo en todas las sucursales donde tiene registro."""
    return list(
        session.execute(
            select(StockSucursal)
            .where(StockSucursal.articulo_id == articulo_id)
            .order_by(StockSucursal.sucursal_id)
        )
        .scalars()
        .all()
    )


def check_available(
    session: Session,
    sucursal_id: int,
    requerido: Iterable[tuple[int, Decimal]],
) -> dict[int, Decimal]:
    """Verifica que haya stock suficiente para cada (articulo_id, cantidad).

    Retorna un dict `{articulo_id: disponible}`. Si alguno no alcanza, levanta
    ValueError con mensaje indicando cuáles son los faltantes.
    """
    faltantes: list[str] = []
    disponibles: dict[int, Decimal] = {}
    for articulo_id, cantidad in requerido:
        row = get_or_create(session, articulo_id, sucursal_id)
        disponibles[articulo_id] = row.cantidad
        if row.cantidad < cantidad:
            faltantes.append(
                f"articulo={articulo_id} requerido={cantidad} disponible={row.cantidad}"
            )
    if faltantes:
        raise ValueError("stock insuficiente: " + "; ".join(faltantes))
    return disponibles


def decrement(
    session: Session, articulo_id: int, sucursal_id: int, cantidad: Decimal
) -> Decimal:
    """Baja stock. No valida; el caller ya validó con `check_available`."""
    row = get_or_create(session, articulo_id, sucursal_id)
    row.cantidad = row.cantidad - cantidad
    return row.cantidad


def increment(
    session: Session, articulo_id: int, sucursal_id: int, cantidad: Decimal
) -> Decimal:
    """Sube stock."""
    row = get_or_create(session, articulo_id, sucursal_id)
    row.cantidad = row.cantidad + cantidad
    return row.cantidad


def set_cantidad(
    session: Session,
    articulo_id: int,
    sucursal_id: int,
    cantidad_nueva: Decimal,
) -> Decimal:
    """Fija el stock a un valor puntual (para ajustes)."""
    row = get_or_create(session, articulo_id, sucursal_id)
    row.cantidad = cantidad_nueva
    return row.cantidad
