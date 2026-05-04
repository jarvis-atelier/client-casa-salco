"""Lógica de aplicación de pagos contra compromisos."""
from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

from app.models.calendario_pago import (
    CompromisoPago,
    EstadoCompromisoEnum,
    PagoCompromiso,
)
from app.models.pago import MedioPagoEnum
from app.models.resumen import MovimientoCaja, TipoMovimientoEnum

if TYPE_CHECKING:
    from app.schemas.calendario_pago import PagoCompromisoCreate

CENTAVO = Decimal("0.01")


class CompromisoValidationError(ValueError):
    """Error de validación al aplicar un pago a un compromiso."""


def _to_decimal(v: Decimal | None) -> Decimal:
    return v if v is not None else Decimal("0")


def _map_medio_pago(medio: str) -> MedioPagoEnum | None:
    """Mapea string libre a `MedioPagoEnum` cuando matchea."""
    try:
        return MedioPagoEnum(medio)
    except ValueError:
        return None


def refrescar_estado(compromiso: CompromisoPago) -> EstadoCompromisoEnum:
    """Recalcula el estado de un compromiso a partir de monto pagado y vencimiento.

    No persiste — el caller hace commit. Mutates `compromiso.estado` y
    eventualmente `compromiso.fecha_pago_real`.
    """
    total = _to_decimal(compromiso.monto_total)
    pagado = _to_decimal(compromiso.monto_pagado)

    # Si el estado fue cancelado manualmente, lo respetamos.
    if compromiso.estado == EstadoCompromisoEnum.cancelado:
        return compromiso.estado

    if pagado >= total - CENTAVO / 2:
        compromiso.estado = EstadoCompromisoEnum.pagado
        if compromiso.fecha_pago_real is None and compromiso.pagos:
            compromiso.fecha_pago_real = max(p.fecha_pago for p in compromiso.pagos)
    elif pagado > Decimal("0"):
        compromiso.estado = EstadoCompromisoEnum.parcial
    elif compromiso.fecha_vencimiento and compromiso.fecha_vencimiento < date.today():
        compromiso.estado = EstadoCompromisoEnum.vencido
    else:
        compromiso.estado = EstadoCompromisoEnum.pendiente

    return compromiso.estado


def aplicar_pago(
    session,
    compromiso: CompromisoPago,
    payload: "PagoCompromisoCreate",
    user_id: int,
) -> PagoCompromiso:
    """Registra un pago contra un compromiso y actualiza estado.

    Si `payload.registrar_movimiento_caja` es True, también crea el
    `MovimientoCaja` correspondiente (tipo `pago_proveedor` si tiene
    proveedor_id, `egreso_efectivo` en otro caso) y queda referenciado
    en `pago.movimiento_caja_id`.

    Lanza `CompromisoValidationError` si:
    - El compromiso ya está pagado o cancelado.
    - El monto excede lo pendiente.
    - Se pide registrar movimiento de caja sin sucursal.
    """
    if compromiso.estado in (
        EstadoCompromisoEnum.pagado,
        EstadoCompromisoEnum.cancelado,
    ):
        raise CompromisoValidationError(
            f"compromiso ya {compromiso.estado.value} — no se puede pagar"
        )

    monto = Decimal(payload.monto)
    if monto <= Decimal("0"):
        raise CompromisoValidationError("monto debe ser mayor a 0")

    pendiente = compromiso.monto_pendiente
    if monto > pendiente + CENTAVO:
        raise CompromisoValidationError(
            f"monto ${monto} excede el pendiente ${pendiente}"
        )

    movimiento: MovimientoCaja | None = None
    if payload.registrar_movimiento_caja:
        sucursal_id = payload.sucursal_id or compromiso.sucursal_id
        if sucursal_id is None:
            raise CompromisoValidationError(
                "sucursal_id requerido para registrar movimiento de caja"
            )

        tipo_mov = (
            TipoMovimientoEnum.pago_proveedor
            if compromiso.proveedor_id
            else TipoMovimientoEnum.egreso_efectivo
        )
        ahora = datetime.now(timezone.utc)
        movimiento = MovimientoCaja(
            sucursal_id=sucursal_id,
            caja_numero=1,
            fecha_caja=payload.fecha_pago,
            fecha=datetime.combine(
                payload.fecha_pago, time(0, 0, tzinfo=timezone.utc)
            ) if payload.fecha_pago != ahora.date() else ahora,
            tipo=tipo_mov,
            medio=_map_medio_pago(payload.medio_pago),
            monto=-monto,  # egreso → negativo
            proveedor_id=compromiso.proveedor_id,
            factura_id=compromiso.factura_id,
            descripcion=f"Pago compromiso #{compromiso.id} — {compromiso.descripcion}"[:200],
            user_id=user_id,
        )
        session.add(movimiento)
        session.flush()  # para obtener movimiento.id

    pago = PagoCompromiso(
        compromiso_id=compromiso.id,
        fecha_pago=payload.fecha_pago,
        monto=monto,
        medio_pago=payload.medio_pago,
        referencia=payload.referencia,
        movimiento_caja_id=movimiento.id if movimiento else None,
        user_id=user_id,
    )
    session.add(pago)

    # Actualizar totales en el compromiso.
    compromiso.monto_pagado = _to_decimal(compromiso.monto_pagado) + monto
    compromiso.pagos.append(pago)
    compromiso.pagado_por_user_id = user_id
    refrescar_estado(compromiso)

    session.flush()
    return pago
