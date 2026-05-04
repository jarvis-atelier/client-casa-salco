"""Generación automática de compromisos de pago.

Dos fuentes:

1. **Facturas tipo C** (compras a proveedores) que no tengan compromiso
   asociado todavía. Default: vence a 30 días de la fecha de la factura.

2. **Tarjetas corporativas activas**: para cada tarjeta con `dia_cierre` ya
   pasado en el mes corriente, crea un compromiso con vencimiento en
   `dia_vencimiento` del próximo mes. Solo si no existe ya uno para ese
   ciclo (proteccion por hash compuesto: tarjeta + año/mes del cierre).

El default del monto del resumen de tarjeta es 0 — el usuario debe editarlo
cuando llega el resumen real. Lo importante acá es generar el placeholder
para que el calendario muestre el vencimiento.
"""
from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import and_, exists, select

from app.models.calendario_pago import (
    CompromisoPago,
    EstadoCompromisoEnum,
    TarjetaCorporativa,
    TipoCompromisoEnum,
)
from app.models.factura import (
    EstadoComprobanteEnum,
    Factura,
    TipoComprobanteEnum,
)


def _safe_day(year: int, month: int, day: int) -> date:
    """Devuelve `date(year, month, day)` clampeando al último día válido."""
    last = monthrange(year, month)[1]
    return date(year, month, min(day, last))


def _next_month(year: int, month: int) -> tuple[int, int]:
    if month == 12:
        return year + 1, 1
    return year, month + 1


def auto_generar_compromisos(
    session,
    user_id: int,
    desde: date | None = None,
) -> dict[str, int]:
    """Genera compromisos automáticos.

    `desde`: solo procesa facturas con fecha >= `desde`. Default: hoy - 60 días.

    Retorna `{creados, desde_facturas, desde_tarjetas}`.
    """
    desde = desde or (date.today() - timedelta(days=60))

    creados_facturas = _generar_desde_facturas_compra(session, user_id, desde)
    creados_tarjetas = _generar_desde_tarjetas(session, user_id)
    creados = creados_facturas + creados_tarjetas

    session.flush()
    return {
        "creados": creados,
        "desde_facturas": creados_facturas,
        "desde_tarjetas": creados_tarjetas,
    }


def _generar_desde_facturas_compra(session, user_id: int, desde: date) -> int:
    """Crea un compromiso por cada factura tipo C que no tenga uno."""
    # Subquery: ya existe un compromiso para esta factura
    existe_subq = exists().where(
        and_(
            CompromisoPago.factura_id == Factura.id,
            CompromisoPago.tipo == TipoCompromisoEnum.factura_compra,
        )
    )
    stmt = (
        select(Factura)
        .where(Factura.tipo == TipoComprobanteEnum.factura_c)
        .where(Factura.estado == EstadoComprobanteEnum.emitida)
        .where(Factura.fecha >= desde)
        .where(~existe_subq)
    )
    facturas = session.execute(stmt).scalars().all()

    creados = 0
    for f in facturas:
        fecha_emision = f.fecha.date() if f.fecha else date.today()
        fecha_venc = fecha_emision + timedelta(days=30)
        descripcion = f"Factura C #{f.punto_venta:04d}-{f.numero:08d}"
        c = CompromisoPago(
            tipo=TipoCompromisoEnum.factura_compra,
            estado=EstadoCompromisoEnum.pendiente,
            descripcion=descripcion[:255],
            monto_total=f.total or Decimal("0"),
            monto_pagado=Decimal("0"),
            fecha_emision=fecha_emision,
            fecha_vencimiento=fecha_venc,
            factura_id=f.id,
            sucursal_id=f.sucursal_id,
            creado_por_user_id=user_id,
        )
        session.add(c)
        creados += 1

    return creados


def _generar_desde_tarjetas(session, user_id: int) -> int:
    """Para cada tarjeta activa, asegura el compromiso del ciclo en curso.

    Si hoy ya pasó el `dia_cierre` del mes, debería existir un compromiso
    cuyo vencimiento sea el `dia_vencimiento` del próximo mes (o de este si
    `dia_vencimiento >= dia_cierre`).
    """
    hoy = date.today()

    tarjetas = (
        session.execute(
            select(TarjetaCorporativa).where(TarjetaCorporativa.activa.is_(True))
        )
        .scalars()
        .all()
    )

    creados = 0
    for t in tarjetas:
        cierre = _safe_day(hoy.year, hoy.month, t.dia_cierre)
        if hoy < cierre:
            # Aún no cerró este mes; no generamos compromiso.
            continue

        # Vencimiento: si dia_vencimiento >= dia_cierre, vence este mes;
        # si no, vence el mes siguiente.
        if t.dia_vencimiento >= t.dia_cierre:
            venc = _safe_day(hoy.year, hoy.month, t.dia_vencimiento)
        else:
            ny, nm = _next_month(hoy.year, hoy.month)
            venc = _safe_day(ny, nm, t.dia_vencimiento)

        # Idempotencia: ¿ya existe un compromiso para esta tarjeta con ese vto?
        ya = session.execute(
            select(CompromisoPago.id)
            .where(CompromisoPago.tarjeta_id == t.id)
            .where(CompromisoPago.fecha_vencimiento == venc)
            .limit(1)
        ).scalar_one_or_none()
        if ya is not None:
            continue

        descripcion = f"Resumen tarjeta {t.nombre} ****{t.ultimos_4}"
        c = CompromisoPago(
            tipo=TipoCompromisoEnum.tarjeta_corporativa,
            estado=EstadoCompromisoEnum.pendiente,
            descripcion=descripcion[:255],
            monto_total=Decimal("0"),  # placeholder hasta que el usuario edite
            monto_pagado=Decimal("0"),
            fecha_emision=cierre,
            fecha_vencimiento=venc,
            tarjeta_id=t.id,
            creado_por_user_id=user_id,
        )
        session.add(c)
        creados += 1

    return creados
