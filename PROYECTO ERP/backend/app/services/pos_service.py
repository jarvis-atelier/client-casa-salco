"""Servicio POS: crear factura completa en una transacción atómica.

Responsabilidades:
  1. Validar sucursal + cliente (si aplica) + artículos activos.
  2. Validar stock disponible para todos los items (solo si controla_stock).
  3. Calcular totales y desglose de IVA por item.
  4. Obtener número secuencial por (sucursal, pv, tipo).
  5. Crear Factura + FacturaItem + FacturaPago + MovimientoCaja.
  6. Decrementar stock por sucursal.
  7. Commit + broadcast socket `factura:emitida`.

La anulación (reverse) reestructura stock y crea movimientos inversos.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.extensions import socketio
from app.models.articulo import Articulo
from app.models.cliente import Cliente
from app.models.factura import (
    EstadoComprobanteEnum,
    Factura,
    TipoComprobanteEnum,
)
from app.models.factura_item import FacturaItem
from app.models.pago import FacturaPago, MedioPagoEnum
from app.models.resumen import MovimientoCaja, TipoMovimientoEnum
from app.models.sucursal import Sucursal
from app.schemas.factura import FacturaCreate

from . import stock_service
from .numeracion import next_numero

TOLERANCIA_PAGOS = Decimal("0.01")
Q2 = Decimal("0.01")
Q4 = Decimal("0.0001")


class POSValidationError(ValueError):
    """Error de validación del POS (422)."""


class POSPermissionError(PermissionError):
    """Error de permisos (403)."""


def _round2(v: Decimal) -> Decimal:
    return v.quantize(Q2, rounding=ROUND_HALF_UP)


def _round4(v: Decimal) -> Decimal:
    return v.quantize(Q4, rounding=ROUND_HALF_UP)


def _calc_linea(
    cantidad: Decimal,
    precio_unitario: Decimal,
    descuento_porc: Decimal,
    iva_porc: Decimal,
) -> tuple[Decimal, Decimal, Decimal, Decimal]:
    """Devuelve (subtotal, iva_monto, total, descuento_monto)."""
    bruto = cantidad * precio_unitario
    descuento_monto = bruto * (descuento_porc / Decimal("100"))
    subtotal = bruto - descuento_monto
    iva_monto = subtotal * (iva_porc / Decimal("100"))
    total = subtotal + iva_monto
    return _round4(subtotal), _round4(iva_monto), _round4(total), _round4(descuento_monto)


def _broadcast_factura_emitida(factura: Factura, sucursal: Sucursal) -> None:
    """Emite evento `factura:emitida` al room `all` del namespace `/prices`.

    Reutilizamos el namespace /prices (ya existe y autentica JWT) para no crear
    un socket nuevo. Los clientes del dashboard filtran por tipo de evento.
    """
    try:
        socketio.emit(
            "factura:emitida",
            {
                "id": factura.id,
                "sucursal": {
                    "id": sucursal.id,
                    "codigo": sucursal.codigo,
                    "nombre": sucursal.nombre,
                },
                "tipo": factura.tipo.value,
                "punto_venta": factura.punto_venta,
                "numero": factura.numero,
                "total": str(factura.total),
                "moneda": factura.moneda,
                "fecha": factura.fecha.isoformat(),
            },
            namespace="/prices",
            to="all",
        )
    except Exception:  # pragma: no cover — defensivo
        pass


def emitir_factura(
    session: Session,
    payload: FacturaCreate,
    cajero_id: int,
) -> Factura:
    """Emite una factura completa de forma atómica.

    Levanta POSValidationError (422) si falla validación de negocio.
    """
    # --- Sucursal
    sucursal = session.get(Sucursal, payload.sucursal_id)
    if sucursal is None or sucursal.deleted_at is not None or not sucursal.activa:
        raise POSValidationError(f"sucursal {payload.sucursal_id} inválida o inactiva")

    # --- Cliente (opcional)
    cliente: Cliente | None = None
    if payload.cliente_id is not None:
        cliente = session.get(Cliente, payload.cliente_id)
        if cliente is None or cliente.deleted_at is not None or not cliente.activo:
            raise POSValidationError(f"cliente {payload.cliente_id} inválido o inactivo")

    # --- Artículos
    articulo_ids = [it.articulo_id for it in payload.items]
    articulos: dict[int, Articulo] = {
        a.id: a
        for a in session.execute(
            select(Articulo).where(Articulo.id.in_(articulo_ids))
        )
        .scalars()
        .all()
    }
    faltantes_art = [aid for aid in articulo_ids if aid not in articulos]
    if faltantes_art:
        raise POSValidationError(
            f"articulo(s) no encontrados: {', '.join(str(x) for x in faltantes_art)}"
        )
    for aid, art in articulos.items():
        if art.deleted_at is not None or not art.activo:
            raise POSValidationError(f"articulo {aid} inactivo")

    # --- Stock (solo los que controlan stock)
    requerido: list[tuple[int, Decimal]] = [
        (it.articulo_id, it.cantidad)
        for it in payload.items
        if articulos[it.articulo_id].controla_stock
    ]
    if requerido:
        try:
            stock_service.check_available(session, payload.sucursal_id, requerido)
        except ValueError as exc:
            raise POSValidationError(str(exc)) from exc

    # --- Cálculo de totales
    subtotal_total = Decimal("0")
    iva_total = Decimal("0")
    descuento_total = Decimal("0")
    total_total = Decimal("0")

    items_calc: list[dict[str, Any]] = []
    for idx, item in enumerate(payload.items):
        art = articulos[item.articulo_id]
        iva_porc = art.iva_porc
        subtotal, iva_monto, total, descuento_monto = _calc_linea(
            item.cantidad, item.precio_unitario, item.descuento_porc, iva_porc
        )
        items_calc.append(
            {
                "articulo": art,
                "item": item,
                "iva_porc": iva_porc,
                "subtotal": subtotal,
                "iva_monto": iva_monto,
                "total": total,
                "descuento_monto": descuento_monto,
                "orden": idx,
            }
        )
        subtotal_total += subtotal
        iva_total += iva_monto
        descuento_total += descuento_monto
        total_total += total

    subtotal_total = _round2(subtotal_total)
    iva_total = _round2(iva_total)
    descuento_total = _round2(descuento_total)
    total_total = _round2(total_total)

    # --- Validación pagos
    suma_pagos = sum((p.monto for p in payload.pagos), Decimal("0"))
    if abs(_round2(suma_pagos) - total_total) > TOLERANCIA_PAGOS:
        raise POSValidationError(
            f"suma de pagos {_round2(suma_pagos)} != total {total_total}"
        )

    # --- Cuenta corriente requiere cliente
    medios_cc = [
        p for p in payload.pagos if p.medio == MedioPagoEnum.cuenta_corriente
    ]
    if medios_cc and cliente is None:
        raise POSValidationError(
            "pago en cuenta corriente requiere cliente (no Consumidor Final)"
        )
    if medios_cc and cliente is not None and not cliente.cuenta_corriente:
        raise POSValidationError(
            f"cliente {cliente.id} no tiene cuenta corriente habilitada"
        )

    # --- Numeración
    numero = next_numero(
        session, payload.sucursal_id, payload.punto_venta, payload.tipo
    )

    # --- Fechas
    ahora = datetime.now(UTC)
    fecha_caja = ahora.date()

    # --- Factura cabecera
    factura = Factura(
        sucursal_id=payload.sucursal_id,
        punto_venta=payload.punto_venta,
        tipo=payload.tipo,
        numero=numero,
        fecha=ahora,
        cliente_id=payload.cliente_id,
        cajero_id=cajero_id,
        estado=EstadoComprobanteEnum.emitida,
        subtotal=subtotal_total,
        total_iva=iva_total,
        total_descuento=descuento_total,
        total=total_total,
        moneda="ARS",
        cotizacion=Decimal("1"),
        observacion=payload.observacion,
    )
    session.add(factura)
    session.flush()

    # --- Items
    for calc in items_calc:
        it: FacturaItem = FacturaItem(
            factura_id=factura.id,
            articulo_id=calc["articulo"].id,
            codigo=calc["articulo"].codigo,
            descripcion=calc["articulo"].descripcion,
            cantidad=calc["item"].cantidad,
            precio_unitario=calc["item"].precio_unitario,
            descuento_porc=calc["item"].descuento_porc,
            iva_porc=calc["iva_porc"],
            iva_monto=calc["iva_monto"],
            subtotal=calc["subtotal"],
            total=calc["total"],
            orden=calc["orden"],
        )
        session.add(it)

    # --- Pagos
    for pidx, pago in enumerate(payload.pagos):
        session.add(
            FacturaPago(
                factura_id=factura.id,
                medio=pago.medio,
                monto=_round2(pago.monto),
                referencia=pago.referencia,
                orden=pidx,
            )
        )

    # --- Movimientos caja (uno por cada pago)
    for pago in payload.pagos:
        session.add(
            MovimientoCaja(
                sucursal_id=payload.sucursal_id,
                caja_numero=1,
                fecha_caja=fecha_caja,
                fecha=ahora,
                tipo=TipoMovimientoEnum.venta,
                medio=pago.medio,
                monto=_round2(pago.monto),
                factura_id=factura.id,
                cliente_id=payload.cliente_id,
                descripcion=(
                    f"Venta {payload.tipo.value} "
                    f"{payload.punto_venta:04d}-{numero:08d}"
                ),
                user_id=cajero_id,
            )
        )

    # --- Stock decrement
    for calc in items_calc:
        if calc["articulo"].controla_stock:
            stock_service.decrement(
                session,
                calc["articulo"].id,
                payload.sucursal_id,
                calc["item"].cantidad,
            )

    # --- Saldo cliente (solo si paga en ctacte)
    if cliente is not None and medios_cc:
        monto_ctacte = sum((p.monto for p in medios_cc), Decimal("0"))
        cliente.saldo = _round2(cliente.saldo + monto_ctacte)

    session.commit()

    _broadcast_factura_emitida(factura, sucursal)

    return factura


def anular_factura(session: Session, factura_id: int, user_id: int) -> Factura:
    """Anula una factura emitida. Revierte stock y crea movimientos devolución."""
    factura = session.get(Factura, factura_id)
    if factura is None:
        raise POSValidationError(f"factura {factura_id} no existe")
    if factura.estado != EstadoComprobanteEnum.emitida:
        raise POSValidationError(
            f"factura {factura_id} no está emitida (estado={factura.estado.value})"
        )

    ahora = datetime.now(UTC)
    fecha_caja = ahora.date()

    factura.estado = EstadoComprobanteEnum.anulada
    factura.anulada_at = ahora
    factura.anulada_por_user_id = user_id

    # Restaurar stock de los items que controlan stock.
    for it in factura.items:
        art = session.get(Articulo, it.articulo_id)
        if art is not None and art.controla_stock:
            stock_service.increment(
                session, it.articulo_id, factura.sucursal_id, it.cantidad
            )

    # Movimientos inversos (uno por pago).
    for pago in factura.pagos:
        session.add(
            MovimientoCaja(
                sucursal_id=factura.sucursal_id,
                caja_numero=1,
                fecha_caja=fecha_caja,
                fecha=ahora,
                tipo=TipoMovimientoEnum.devolucion,
                medio=pago.medio,
                monto=-_round2(pago.monto),
                factura_id=factura.id,
                cliente_id=factura.cliente_id,
                descripcion=(
                    f"Anulación {factura.tipo.value} "
                    f"{factura.punto_venta:04d}-{factura.numero:08d}"
                ),
                user_id=user_id,
            )
        )

    # Revertir saldo del cliente (si pago en ctacte).
    if factura.cliente_id is not None:
        monto_ctacte = sum(
            (p.monto for p in factura.pagos if p.medio == MedioPagoEnum.cuenta_corriente),
            Decimal("0"),
        )
        if monto_ctacte > 0:
            cliente = session.get(Cliente, factura.cliente_id)
            if cliente is not None:
                cliente.saldo = _round2(cliente.saldo - monto_ctacte)

    session.commit()
    return factura
