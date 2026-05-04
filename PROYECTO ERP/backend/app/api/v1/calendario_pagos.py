"""Endpoints del módulo Calendario de pagos.

Compromisos, tarjetas corporativas y pagos parciales.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Any

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models.calendario_pago import (
    CompromisoPago,
    EstadoCompromisoEnum,
    PagoCompromiso,
    TarjetaCorporativa,
    TipoCompromisoEnum,
)
from app.models.proveedor import Proveedor
from app.schemas.calendario_pago import (
    AutoGenerarResult,
    CalendarDayOut,
    CompromisoPagoCreate,
    CompromisoPagoDetalleOut,
    CompromisoPagoOut,
    CompromisoPagoPatch,
    CompromisoResumen,
    PagoCompromisoCreate,
    PagoCompromisoOut,
    TarjetaCorporativaCreate,
    TarjetaCorporativaOut,
    TarjetaCorporativaPatch,
)
from app.services.calendario_pagos import (
    CompromisoValidationError,
    aplicar_pago,
    auto_generar_compromisos,
    refrescar_estado,
)
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response
from app.utils.pagination import get_page_params, paginate_query

bp = Blueprint("calendario_pagos", __name__, url_prefix="/api/v1")


SEVERIDAD_ORDER = {"baja": 0, "media": 1, "alta": 2, "critica": 3}


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _user_id() -> int:
    try:
        return int(get_jwt_identity())
    except (TypeError, ValueError) as exc:
        raise ValueError("token inválido") from exc


def _severidad_de_compromiso(c: CompromisoPago, hoy: date) -> str:
    """Severidad visual para el dot del calendario."""
    dias = (c.fecha_vencimiento - hoy).days
    if c.estado == EstadoCompromisoEnum.pagado:
        return "baja"
    if dias < 0:
        return "critica"
    if dias == 0:
        return "alta"
    if dias <= 3:
        return "media"
    return "baja"


# ---------------------------------------------------------------------------
# Compromisos — listado paginado
# ---------------------------------------------------------------------------


@bp.get("/compromisos")
@roles_required("admin", "supervisor", "contador")
def list_compromisos():
    estado = request.args.get("estado")
    tipo = request.args.get("tipo")
    proveedor_id = request.args.get("proveedor_id", type=int)
    tarjeta_id = request.args.get("tarjeta_id", type=int)
    fecha_desde = _parse_date(request.args.get("fecha_desde"))
    fecha_hasta = _parse_date(request.args.get("fecha_hasta"))

    stmt = select(CompromisoPago)

    if estado:
        try:
            stmt = stmt.where(CompromisoPago.estado == EstadoCompromisoEnum(estado))
        except ValueError:
            return error_response(f"estado inválido: {estado}", 422, "validation_error")

    if tipo:
        try:
            stmt = stmt.where(CompromisoPago.tipo == TipoCompromisoEnum(tipo))
        except ValueError:
            return error_response(f"tipo inválido: {tipo}", 422, "validation_error")

    if proveedor_id is not None:
        stmt = stmt.where(CompromisoPago.proveedor_id == proveedor_id)
    if tarjeta_id is not None:
        stmt = stmt.where(CompromisoPago.tarjeta_id == tarjeta_id)
    if fecha_desde:
        stmt = stmt.where(CompromisoPago.fecha_vencimiento >= fecha_desde)
    if fecha_hasta:
        stmt = stmt.where(CompromisoPago.fecha_vencimiento <= fecha_hasta)

    stmt = stmt.order_by(
        CompromisoPago.fecha_vencimiento.asc(), CompromisoPago.id.asc()
    )

    page, per_page = get_page_params()
    return jsonify(paginate_query(stmt, CompromisoPagoOut, page, per_page))


# ---------------------------------------------------------------------------
# Compromisos — resumen para stat cards
# ---------------------------------------------------------------------------


@bp.get("/compromisos/resumen")
@roles_required("admin", "supervisor", "contador")
def get_resumen():
    hoy = date.today()
    fin_semana = hoy + timedelta(days=7)
    fin_mes = hoy + timedelta(days=30)

    abiertos = (
        select(CompromisoPago)
        .where(
            CompromisoPago.estado.in_(
                [
                    EstadoCompromisoEnum.pendiente,
                    EstadoCompromisoEnum.parcial,
                    EstadoCompromisoEnum.vencido,
                ]
            )
        )
    )

    rows = db.session.execute(abiertos).scalars().all()

    vencidos = 0
    vence_hoy = 0
    esta_semana = 0
    este_mes = 0
    total_pendiente = Decimal("0")
    total_vencido = Decimal("0")

    for c in rows:
        pendiente = c.monto_pendiente
        if pendiente <= 0:
            continue
        total_pendiente += pendiente
        if c.fecha_vencimiento < hoy:
            vencidos += 1
            total_vencido += pendiente
        elif c.fecha_vencimiento == hoy:
            vence_hoy += 1
            esta_semana += 1
            este_mes += 1
        elif c.fecha_vencimiento <= fin_semana:
            esta_semana += 1
            este_mes += 1
        elif c.fecha_vencimiento <= fin_mes:
            este_mes += 1

    return jsonify(
        CompromisoResumen(
            vencidos=vencidos,
            vence_hoy=vence_hoy,
            esta_semana=esta_semana,
            este_mes=este_mes,
            total_pendiente=total_pendiente,
            total_vencido=total_vencido,
        ).model_dump(mode="json")
    )


# ---------------------------------------------------------------------------
# Compromisos — calendario (agrupados por día)
# ---------------------------------------------------------------------------


@bp.get("/compromisos/calendar")
@roles_required("admin", "supervisor", "contador")
def get_calendar():
    mes_str = request.args.get("mes")  # YYYY-MM
    if not mes_str:
        hoy = date.today()
        anio, mes = hoy.year, hoy.month
    else:
        try:
            anio, mes = (int(p) for p in mes_str.split("-")[:2])
        except (ValueError, IndexError):
            return error_response("formato de mes inválido (YYYY-MM)", 422, "validation_error")

    primero = date(anio, mes, 1)
    if mes == 12:
        primero_siguiente = date(anio + 1, 1, 1)
    else:
        primero_siguiente = date(anio, mes + 1, 1)

    rows = (
        db.session.execute(
            select(CompromisoPago)
            .where(CompromisoPago.fecha_vencimiento >= primero)
            .where(CompromisoPago.fecha_vencimiento < primero_siguiente)
            .order_by(CompromisoPago.fecha_vencimiento.asc())
        )
        .scalars()
        .all()
    )

    hoy = date.today()
    grupos: dict[date, list[CompromisoPago]] = defaultdict(list)
    for c in rows:
        grupos[c.fecha_vencimiento].append(c)

    out: list[dict[str, Any]] = []
    for fecha, comps in sorted(grupos.items()):
        sev_max = "baja"
        monto_total = Decimal("0")
        ids: list[int] = []
        for c in comps:
            sev = _severidad_de_compromiso(c, hoy)
            if SEVERIDAD_ORDER[sev] > SEVERIDAD_ORDER[sev_max]:
                sev_max = sev
            monto_total += c.monto_pendiente if c.monto_pendiente > 0 else Decimal("0")
            ids.append(c.id)
        out.append(
            CalendarDayOut(
                fecha=fecha,
                cantidad=len(comps),
                monto_total=monto_total,
                severidad_max=sev_max,
                compromisos_ids=ids,
            ).model_dump(mode="json")
        )

    return jsonify(items=out, mes=f"{anio:04d}-{mes:02d}")


# ---------------------------------------------------------------------------
# Compromisos — auto-generar
# ---------------------------------------------------------------------------


@bp.post("/compromisos/auto-generar")
@roles_required("admin", "supervisor")
def auto_generar():
    try:
        user_id = _user_id()
    except ValueError:
        return error_response("token inválido", 401, "invalid_token")

    body = request.get_json(silent=True) or {}
    desde = _parse_date(body.get("desde"))

    result = auto_generar_compromisos(db.session, user_id=user_id, desde=desde)
    db.session.commit()
    return jsonify(AutoGenerarResult(**result).model_dump())


# ---------------------------------------------------------------------------
# Compromisos — detalle
# ---------------------------------------------------------------------------


@bp.get("/compromisos/<int:compromiso_id>")
@roles_required("admin", "supervisor", "contador")
def get_compromiso(compromiso_id: int):
    compromiso = db.session.execute(
        select(CompromisoPago)
        .options(
            selectinload(CompromisoPago.pagos),
            selectinload(CompromisoPago.proveedor),
            selectinload(CompromisoPago.tarjeta),
        )
        .where(CompromisoPago.id == compromiso_id)
    ).scalar_one_or_none()
    if compromiso is None:
        return error_response("compromiso no encontrado", 404, "not_found")

    base = CompromisoPagoDetalleOut.model_validate(compromiso).model_dump(mode="json")
    base["pagos"] = [
        PagoCompromisoOut.model_validate(p).model_dump(mode="json")
        for p in compromiso.pagos
    ]
    base["proveedor_nombre"] = (
        compromiso.proveedor.razon_social if compromiso.proveedor else None
    )
    base["tarjeta_nombre"] = (
        compromiso.tarjeta.nombre if compromiso.tarjeta else None
    )
    return jsonify(base)


# ---------------------------------------------------------------------------
# Compromisos — crear
# ---------------------------------------------------------------------------


@bp.post("/compromisos")
@roles_required("admin", "supervisor")
def create_compromiso():
    try:
        payload = CompromisoPagoCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    try:
        user_id = _user_id()
    except ValueError:
        return error_response("token inválido", 401, "invalid_token")

    if payload.proveedor_id is not None:
        existe = db.session.get(Proveedor, payload.proveedor_id)
        if existe is None:
            return error_response("proveedor no encontrado", 422, "validation_error")

    compromiso = CompromisoPago(
        tipo=payload.tipo,
        descripcion=payload.descripcion,
        monto_total=payload.monto_total,
        monto_pagado=Decimal("0"),
        fecha_emision=payload.fecha_emision,
        fecha_vencimiento=payload.fecha_vencimiento,
        proveedor_id=payload.proveedor_id,
        factura_id=payload.factura_id,
        tarjeta_id=payload.tarjeta_id,
        sucursal_id=payload.sucursal_id,
        nota=payload.nota,
        creado_por_user_id=user_id,
    )
    refrescar_estado(compromiso)
    db.session.add(compromiso)
    db.session.commit()
    return jsonify(CompromisoPagoOut.model_validate(compromiso).model_dump(mode="json")), 201


# ---------------------------------------------------------------------------
# Compromisos — editar
# ---------------------------------------------------------------------------


@bp.patch("/compromisos/<int:compromiso_id>")
@roles_required("admin", "supervisor")
def patch_compromiso(compromiso_id: int):
    try:
        payload = CompromisoPagoPatch.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )

    compromiso = db.session.get(CompromisoPago, compromiso_id)
    if compromiso is None:
        return error_response("compromiso no encontrado", 404, "not_found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(compromiso, k, v)
    refrescar_estado(compromiso)
    db.session.commit()
    return jsonify(CompromisoPagoOut.model_validate(compromiso).model_dump(mode="json"))


# ---------------------------------------------------------------------------
# Compromisos — eliminar (sólo si pendiente y sin pagos)
# ---------------------------------------------------------------------------


@bp.delete("/compromisos/<int:compromiso_id>")
@roles_required("admin", "supervisor")
def delete_compromiso(compromiso_id: int):
    compromiso = db.session.get(CompromisoPago, compromiso_id)
    if compromiso is None:
        return error_response("compromiso no encontrado", 404, "not_found")
    if compromiso.estado != EstadoCompromisoEnum.pendiente:
        return error_response(
            "sólo se pueden eliminar compromisos en estado pendiente",
            422,
            "invalid_state",
        )
    pagos_count = db.session.scalar(
        select(func.count(PagoCompromiso.id)).where(
            PagoCompromiso.compromiso_id == compromiso_id
        )
    )
    if pagos_count and pagos_count > 0:
        return error_response(
            "no se puede eliminar — tiene pagos registrados",
            422,
            "invalid_state",
        )
    db.session.delete(compromiso)
    db.session.commit()
    return jsonify(deleted=True, id=compromiso_id)


# ---------------------------------------------------------------------------
# Compromisos — registrar pago
# ---------------------------------------------------------------------------


@bp.post("/compromisos/<int:compromiso_id>/pagar")
@roles_required("admin", "supervisor")
def pagar_compromiso(compromiso_id: int):
    try:
        payload = PagoCompromisoCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    try:
        user_id = _user_id()
    except ValueError:
        return error_response("token inválido", 401, "invalid_token")

    compromiso = db.session.get(CompromisoPago, compromiso_id)
    if compromiso is None:
        return error_response("compromiso no encontrado", 404, "not_found")

    try:
        pago = aplicar_pago(db.session, compromiso, payload, user_id=user_id)
    except CompromisoValidationError as err:
        db.session.rollback()
        return error_response(str(err), 422, "validation_error")

    db.session.commit()
    return (
        jsonify(
            {
                "pago": PagoCompromisoOut.model_validate(pago).model_dump(mode="json"),
                "compromiso": CompromisoPagoOut.model_validate(compromiso).model_dump(mode="json"),
            }
        ),
        201,
    )


# ---------------------------------------------------------------------------
# Tarjetas corporativas — CRUD
# ---------------------------------------------------------------------------


@bp.get("/tarjetas")
@roles_required("admin", "supervisor", "contador")
def list_tarjetas():
    rows = (
        db.session.execute(
            select(TarjetaCorporativa).order_by(TarjetaCorporativa.nombre.asc())
        )
        .scalars()
        .all()
    )
    return jsonify(
        items=[TarjetaCorporativaOut.model_validate(r).model_dump(mode="json") for r in rows]
    )


@bp.post("/tarjetas")
@roles_required("admin", "supervisor")
def create_tarjeta():
    try:
        payload = TarjetaCorporativaCreate.model_validate(
            request.get_json(silent=True) or {}
        )
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    t = TarjetaCorporativa(**payload.model_dump())
    db.session.add(t)
    db.session.commit()
    return (
        jsonify(TarjetaCorporativaOut.model_validate(t).model_dump(mode="json")),
        201,
    )


@bp.patch("/tarjetas/<int:tarjeta_id>")
@roles_required("admin", "supervisor")
def patch_tarjeta(tarjeta_id: int):
    try:
        payload = TarjetaCorporativaPatch.model_validate(
            request.get_json(silent=True) or {}
        )
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    t = db.session.get(TarjetaCorporativa, tarjeta_id)
    if t is None:
        return error_response("tarjeta no encontrada", 404, "not_found")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(t, k, v)
    db.session.commit()
    return jsonify(TarjetaCorporativaOut.model_validate(t).model_dump(mode="json"))


@bp.delete("/tarjetas/<int:tarjeta_id>")
@roles_required("admin", "supervisor")
def delete_tarjeta(tarjeta_id: int):
    t = db.session.get(TarjetaCorporativa, tarjeta_id)
    if t is None:
        return error_response("tarjeta no encontrada", 404, "not_found")
    # Si tiene compromisos, mejor desactivamos en lugar de borrar.
    referenciada = db.session.scalar(
        select(func.count(CompromisoPago.id)).where(
            CompromisoPago.tarjeta_id == tarjeta_id
        )
    )
    if referenciada and referenciada > 0:
        t.activa = False
        db.session.commit()
        return jsonify(deactivated=True, id=tarjeta_id)
    db.session.delete(t)
    db.session.commit()
    return jsonify(deleted=True, id=tarjeta_id)
