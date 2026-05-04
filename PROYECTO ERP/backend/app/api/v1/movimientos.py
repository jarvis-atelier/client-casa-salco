"""Endpoints de movimientos de caja (ledger universal)."""
from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select

from app.extensions import db
from app.models.pago import MedioPagoEnum
from app.models.resumen import MovimientoCaja, TipoMovimientoEnum
from app.schemas.movimiento_caja import MovimientoCajaOut
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response
from app.utils.pagination import get_page_params, paginate_query

bp = Blueprint("movimientos", __name__, url_prefix="/api/v1/movimientos")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@bp.get("")
@roles_required("admin", "supervisor", "cajero", "contador")
def list_movimientos():
    claims = get_jwt()
    rol = claims.get("rol")
    user_sucursal = claims.get("sucursal_id")

    sucursal_id = request.args.get("sucursal_id", type=int)
    tipo = request.args.get("tipo")
    fecha_desde = _parse_date(request.args.get("fecha_desde"))
    fecha_hasta = _parse_date(request.args.get("fecha_hasta"))
    cliente_id = request.args.get("cliente_id", type=int)
    caja_numero = request.args.get("caja_numero", type=int)

    stmt = select(MovimientoCaja)

    if rol == "cajero" and user_sucursal:
        stmt = stmt.where(MovimientoCaja.sucursal_id == user_sucursal)
    elif sucursal_id:
        stmt = stmt.where(MovimientoCaja.sucursal_id == sucursal_id)

    if tipo:
        try:
            tipo_enum = TipoMovimientoEnum(tipo)
            stmt = stmt.where(MovimientoCaja.tipo == tipo_enum)
        except ValueError:
            return error_response(f"tipo inválido: {tipo}", 422, "validation_error")

    if cliente_id:
        stmt = stmt.where(MovimientoCaja.cliente_id == cliente_id)

    if caja_numero is not None:
        stmt = stmt.where(MovimientoCaja.caja_numero == caja_numero)

    if fecha_desde:
        stmt = stmt.where(
            MovimientoCaja.fecha >= datetime.combine(fecha_desde, datetime.min.time())
        )
    if fecha_hasta:
        stmt = stmt.where(
            MovimientoCaja.fecha <= datetime.combine(fecha_hasta, datetime.max.time())
        )

    stmt = stmt.order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc())
    page, per_page = get_page_params()
    return jsonify(paginate_query(stmt, MovimientoCajaOut, page, per_page))


# ---------------------------------------------------------------------------
# Apertura / cierre de caja
# ---------------------------------------------------------------------------


class _AbrirCajaPayload(BaseModel):
    sucursal_id: int
    caja_numero: int = 1
    monto_inicial: Decimal = Field(default=Decimal("0"), ge=0)
    observacion: str | None = None


class _CerrarCajaPayload(BaseModel):
    sucursal_id: int
    caja_numero: int = 1
    conteo_efectivo: Decimal = Field(ge=0)
    observacion: str | None = None


def _check_sucursal_access(claims: dict, sucursal_id: int) -> str | None:
    """Devuelve None si OK, o un mensaje de error 403."""
    rol = claims.get("rol")
    user_sucursal = claims.get("sucursal_id")
    if rol == "cajero" and user_sucursal not in (None, sucursal_id):
        return f"cajero de sucursal {user_sucursal} no puede operar en sucursal {sucursal_id}"
    return None


def _last_apertura(sucursal_id: int, caja_numero: int) -> MovimientoCaja | None:
    stmt = (
        select(MovimientoCaja)
        .where(
            MovimientoCaja.sucursal_id == sucursal_id,
            MovimientoCaja.caja_numero == caja_numero,
            MovimientoCaja.tipo == TipoMovimientoEnum.apertura_caja,
        )
        .order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc())
        .limit(1)
    )
    return db.session.execute(stmt).scalar_one_or_none()


def _last_cierre(sucursal_id: int, caja_numero: int) -> MovimientoCaja | None:
    stmt = (
        select(MovimientoCaja)
        .where(
            MovimientoCaja.sucursal_id == sucursal_id,
            MovimientoCaja.caja_numero == caja_numero,
            MovimientoCaja.tipo == TipoMovimientoEnum.cierre_caja,
        )
        .order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc())
        .limit(1)
    )
    return db.session.execute(stmt).scalar_one_or_none()


def _caja_abierta(sucursal_id: int, caja_numero: int) -> MovimientoCaja | None:
    apertura = _last_apertura(sucursal_id, caja_numero)
    if apertura is None:
        return None
    cierre = _last_cierre(sucursal_id, caja_numero)
    if cierre is not None and cierre.fecha >= apertura.fecha:
        return None
    return apertura


@bp.post("/abrir-caja")
@roles_required("admin", "supervisor", "cajero")
def abrir_caja():
    try:
        payload = _AbrirCajaPayload.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )

    claims = get_jwt()
    err = _check_sucursal_access(claims, payload.sucursal_id)
    if err is not None:
        return error_response(err, 403, "forbidden_sucursal")

    if _caja_abierta(payload.sucursal_id, payload.caja_numero) is not None:
        return error_response(
            f"caja {payload.caja_numero} de sucursal {payload.sucursal_id} ya está abierta",
            409,
            "caja_ya_abierta",
        )

    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        user_id = None

    now = datetime.now(UTC)
    mov = MovimientoCaja(
        sucursal_id=payload.sucursal_id,
        caja_numero=payload.caja_numero,
        fecha_caja=now.date(),
        fecha=now,
        tipo=TipoMovimientoEnum.apertura_caja,
        medio=MedioPagoEnum.efectivo,
        monto=payload.monto_inicial,
        descripcion=(payload.observacion or "Apertura de caja"),
        user_id=user_id,
    )
    db.session.add(mov)
    db.session.commit()

    return (
        jsonify(
            {
                "movimiento": MovimientoCajaOut.model_validate(mov).model_dump(mode="json"),
                "caja_abierta": True,
            }
        ),
        201,
    )


def _totales_dia(sucursal_id: int, caja_numero: int, fecha_caja: date) -> dict[str, Any]:
    """Calcula totales del día por medio + ingresos/egresos."""
    rows = (
        db.session.execute(
            select(MovimientoCaja).where(
                MovimientoCaja.sucursal_id == sucursal_id,
                MovimientoCaja.caja_numero == caja_numero,
                MovimientoCaja.fecha_caja == fecha_caja,
            )
        )
        .scalars()
        .all()
    )

    ingresos_tipos = {
        TipoMovimientoEnum.venta,
        TipoMovimientoEnum.cobranza,
        TipoMovimientoEnum.ingreso_efectivo,
        TipoMovimientoEnum.cheque_recibido,
    }
    egresos_tipos = {
        TipoMovimientoEnum.devolucion,
        TipoMovimientoEnum.pago_proveedor,
        TipoMovimientoEnum.egreso_efectivo,
        TipoMovimientoEnum.cheque_entregado,
    }

    por_medio: dict[str, Decimal] = {}
    ingresos = Decimal("0")
    egresos = Decimal("0")
    teorico_efectivo = Decimal("0")
    apertura_monto = Decimal("0")

    for r in rows:
        monto = Decimal(r.monto)
        if r.medio is not None:
            key = r.medio.value
            signed = -abs(monto) if r.tipo in egresos_tipos else monto
            por_medio[key] = por_medio.get(key, Decimal("0")) + signed
        if r.tipo in ingresos_tipos:
            ingresos += abs(monto)
        elif r.tipo in egresos_tipos:
            egresos += abs(monto)
        if r.tipo == TipoMovimientoEnum.apertura_caja:
            apertura_monto += monto
        # Sumar al teórico efectivo solo si el medio es efectivo
        if r.medio == MedioPagoEnum.efectivo:
            if r.tipo == TipoMovimientoEnum.apertura_caja:
                teorico_efectivo += monto
            elif r.tipo in ingresos_tipos:
                teorico_efectivo += abs(monto)
            elif r.tipo in egresos_tipos:
                teorico_efectivo -= abs(monto)

    return {
        "totales_por_medio": {k: str(v) for k, v in por_medio.items()},
        "ingresos": str(ingresos),
        "egresos": str(egresos),
        "teorico_efectivo": str(teorico_efectivo),
        "apertura_monto": str(apertura_monto),
        "cantidad_movimientos": len(rows),
    }


@bp.post("/cerrar-caja")
@roles_required("admin", "supervisor", "cajero")
def cerrar_caja():
    try:
        payload = _CerrarCajaPayload.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )

    claims = get_jwt()
    err = _check_sucursal_access(claims, payload.sucursal_id)
    if err is not None:
        return error_response(err, 403, "forbidden_sucursal")

    apertura = _caja_abierta(payload.sucursal_id, payload.caja_numero)
    if apertura is None:
        return error_response(
            f"caja {payload.caja_numero} de sucursal {payload.sucursal_id} no está abierta",
            409,
            "caja_no_abierta",
        )

    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        user_id = None

    totales = _totales_dia(
        payload.sucursal_id, payload.caja_numero, apertura.fecha_caja
    )
    teorico = Decimal(totales["teorico_efectivo"])
    diferencia = payload.conteo_efectivo - teorico

    now = datetime.now(UTC)
    descripcion_parts = [
        f"Cierre conteo {payload.conteo_efectivo} teórico {teorico}",
    ]
    if payload.observacion:
        descripcion_parts.append(payload.observacion.strip())
    mov = MovimientoCaja(
        sucursal_id=payload.sucursal_id,
        caja_numero=payload.caja_numero,
        fecha_caja=apertura.fecha_caja,
        fecha=now,
        tipo=TipoMovimientoEnum.cierre_caja,
        medio=MedioPagoEnum.efectivo,
        monto=diferencia,
        descripcion=" — ".join(descripcion_parts),
        user_id=user_id,
    )
    db.session.add(mov)
    db.session.commit()

    return (
        jsonify(
            {
                "movimiento": MovimientoCajaOut.model_validate(mov).model_dump(mode="json"),
                "teorico_efectivo": totales["teorico_efectivo"],
                "conteo_efectivo": str(payload.conteo_efectivo),
                "diferencia": str(diferencia),
                "totales_por_medio": totales["totales_por_medio"],
                "ingresos": totales["ingresos"],
                "egresos": totales["egresos"],
                "fecha_caja": apertura.fecha_caja.isoformat(),
            }
        ),
        201,
    )


@bp.get("/estado-caja")
@roles_required("admin", "supervisor", "cajero", "contador")
def estado_caja():
    sucursal_id = request.args.get("sucursal_id", type=int)
    caja_numero = request.args.get("caja_numero", type=int, default=1)
    if sucursal_id is None:
        return error_response("sucursal_id requerido", 422, "validation_error")

    claims = get_jwt()
    err = _check_sucursal_access(claims, sucursal_id)
    if err is not None:
        return error_response(err, 403, "forbidden_sucursal")

    apertura = _caja_abierta(sucursal_id, caja_numero)
    abierta = apertura is not None

    fecha_caja = apertura.fecha_caja if apertura else date.today()
    totales = _totales_dia(sucursal_id, caja_numero, fecha_caja)

    # cantidad total de movimientos del día (sin filtrar por caja para el resumen general
    # del día? No: queremos ese cajero/caja).
    total_movs = db.session.scalar(
        select(func.count(MovimientoCaja.id)).where(
            MovimientoCaja.sucursal_id == sucursal_id,
            MovimientoCaja.caja_numero == caja_numero,
            MovimientoCaja.fecha_caja == fecha_caja,
        )
    ) or 0

    return jsonify(
        {
            "abierta": abierta,
            "abierta_desde": apertura.fecha.isoformat() if apertura else None,
            "fecha_caja": fecha_caja.isoformat(),
            "sucursal_id": sucursal_id,
            "caja_numero": caja_numero,
            "total_movimientos_hoy": int(total_movs),
            "totales_por_medio": totales["totales_por_medio"],
            "ingresos": totales["ingresos"],
            "egresos": totales["egresos"],
            "teorico_efectivo": totales["teorico_efectivo"],
        }
    )
