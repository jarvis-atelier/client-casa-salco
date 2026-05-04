"""Cálculo de velocidad de venta de un articulo en una sucursal.

Devuelve métricas de demanda histórica:
- cantidad_total_vendida (en N días)
- velocidad_promedio_diaria (cantidad / N días)
- dias_con_venta (días distintos que tuvieron al menos una venta)
- desviacion_estandar de la cantidad diaria

Filtra por facturas tipo venta emitidas (ticket / factura A/B/C).
Excluye notas de crédito y remitos. NO descuenta devoluciones — el use case
es estimar demanda, no inventario.
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.factura import EstadoComprobanteEnum, Factura, TipoComprobanteEnum
from app.models.factura_item import FacturaItem


VENTA_TIPOS = (
    TipoComprobanteEnum.factura_a,
    TipoComprobanteEnum.factura_b,
    TipoComprobanteEnum.factura_c,
    TipoComprobanteEnum.ticket,
)


def calcular_velocidad_venta(
    session: Session,
    articulo_id: int,
    sucursal_id: int | None = None,
    dias: int = 30,
) -> dict:
    """Calcula velocidad de venta del articulo en últimos N días.

    Args:
        session: SQLAlchemy session.
        articulo_id: id del articulo.
        sucursal_id: opcional. Si None, agrega todas las sucursales.
        dias: ventana en días (default 30).

    Returns:
        dict con keys:
            - articulo_id
            - sucursal_id
            - dias
            - cantidad_total_vendida (Decimal)
            - velocidad_promedio_diaria (Decimal, cantidad/dias)
            - dias_con_venta (int)
            - velocidad_dias_activos (Decimal, cantidad / dias_con_venta o 0)
            - desviacion_estandar (Decimal)
            - desde (ISO date)
            - hasta (ISO date)
    """
    if dias < 1:
        dias = 1
    hasta = datetime.now(timezone.utc)
    desde = hasta - timedelta(days=dias)

    where = [
        Factura.fecha >= desde,
        Factura.fecha <= hasta,
        Factura.estado == EstadoComprobanteEnum.emitida,
        Factura.tipo.in_(VENTA_TIPOS),
        FacturaItem.articulo_id == articulo_id,
    ]
    if sucursal_id is not None:
        where.append(Factura.sucursal_id == sucursal_id)

    # Sumar cantidad por día (date_trunc compatible con sqlite y postgres)
    try:
        dialect_name = session.get_bind().dialect.name
    except Exception:
        dialect_name = "sqlite"
    if dialect_name == "postgresql":
        dia_col = func.date_trunc("day", Factura.fecha)
    else:
        dia_col = func.strftime("%Y-%m-%d", Factura.fecha)

    stmt = (
        select(
            dia_col.label("dia"),
            func.coalesce(func.sum(FacturaItem.cantidad), 0).label("qty"),
        )
        .select_from(FacturaItem)
        .join(Factura, Factura.id == FacturaItem.factura_id)
        .where(*where)
        .group_by(dia_col)
    )

    rows = session.execute(stmt).all()

    cantidades_por_dia: list[Decimal] = []
    cantidad_total = Decimal("0")
    for r in rows:
        q = Decimal(str(r.qty)) if r.qty is not None else Decimal("0")
        cantidades_por_dia.append(q)
        cantidad_total += q

    dias_con_venta = len(cantidades_por_dia)
    velocidad_promedio = (cantidad_total / Decimal(dias)) if dias > 0 else Decimal("0")
    velocidad_dias_activos = (
        (cantidad_total / Decimal(dias_con_venta))
        if dias_con_venta > 0
        else Decimal("0")
    )

    # Desviación estándar poblacional sobre días con venta (más estable que
    # incluir los ceros).
    if dias_con_venta > 1:
        media = float(velocidad_dias_activos)
        var = sum((float(q) - media) ** 2 for q in cantidades_por_dia) / dias_con_venta
        desv = Decimal(str(math.sqrt(var))).quantize(Decimal("0.0001"))
    else:
        desv = Decimal("0")

    return {
        "articulo_id": articulo_id,
        "sucursal_id": sucursal_id,
        "dias": dias,
        "cantidad_total_vendida": cantidad_total.quantize(Decimal("0.0001")),
        "velocidad_promedio_diaria": velocidad_promedio.quantize(Decimal("0.0001")),
        "dias_con_venta": dias_con_venta,
        "velocidad_dias_activos": velocidad_dias_activos.quantize(Decimal("0.0001")),
        "desviacion_estandar": desv,
        "desde": desde.date().isoformat(),
        "hasta": hasta.date().isoformat(),
    }


def calcular_quiebres_stock(
    session: Session,
    articulo_id: int,
    sucursal_id: int,
    dias: int = 30,
) -> int:
    """Cuenta cuántos días distintos en últimos N días el articulo se quedó
    en cantidad <= 0 mirando los movimientos de ajuste.

    Heurística: contamos ajustes negativos cuya descripcion menciona el id del
    articulo. Como no hay un evento de "stockout" formal, esto es proxy y se
    refina cuando exista un módulo de movimientos de stock por articulo.
    Por ahora se limita a contar veces que el ajuste mencionó este articulo.
    """
    # Implementación simple — placeholder. La señal real de quiebres exige un
    # historial de stock por día (aún no implementado). Devuelve 0 si no hay
    # movimientos coincidentes.
    from app.models.resumen import MovimientoCaja, TipoMovimientoEnum

    desde = datetime.now(timezone.utc) - timedelta(days=dias)
    pattern = f"%art={articulo_id}%"
    stmt = (
        select(func.count(MovimientoCaja.id))
        .where(
            MovimientoCaja.tipo == TipoMovimientoEnum.ajuste,
            MovimientoCaja.fecha >= desde,
            MovimientoCaja.sucursal_id == sucursal_id,
            MovimientoCaja.descripcion.like(pattern),
            MovimientoCaja.descripcion.like("%→0%"),
        )
    )
    return int(session.scalar(stmt) or 0)


__all__ = ["calcular_velocidad_venta", "calcular_quiebres_stock"]
