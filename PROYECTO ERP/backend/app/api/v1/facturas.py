"""Endpoints de facturación — POS (crear venta completa) + listar + anular."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models.factura import Factura, TipoComprobanteEnum
from app.schemas.factura import ClienteResumen, FacturaCreate, FacturaOut
from app.services.pos_service import (
    POSPermissionError,
    POSValidationError,
    anular_factura,
    emitir_factura,
)
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response
from app.utils.pagination import get_page_params, paginate_query

bp = Blueprint("facturas", __name__, url_prefix="/api/v1/facturas")


def _serialize_factura(factura: Factura) -> dict[str, Any]:
    """Serializa con FacturaOut + agrega cliente_resumen / cliente_nombre."""
    out = FacturaOut.model_validate(factura).model_dump(mode="json")
    if factura.cliente is not None:
        resumen = ClienteResumen.model_validate(factura.cliente)
        out["cliente_resumen"] = resumen.model_dump(mode="json")
        out["cliente_nombre"] = factura.cliente.razon_social
    else:
        out["cliente_resumen"] = None
        out["cliente_nombre"] = None
    return out


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


@bp.post("")
@roles_required("admin", "supervisor", "cajero")
def create_factura():
    try:
        payload = FacturaCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )

    claims = get_jwt()
    try:
        cajero_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return error_response("token inválido", 401, "invalid_token")

    rol = claims.get("rol")
    user_sucursal = claims.get("sucursal_id")

    # Cajero sólo puede emitir en su sucursal asignada.
    if rol == "cajero" and user_sucursal not in (None, payload.sucursal_id):
        return error_response(
            f"cajero de sucursal {user_sucursal} no puede facturar en sucursal {payload.sucursal_id}",
            403,
            "forbidden_sucursal",
        )

    try:
        factura = emitir_factura(db.session, payload, cajero_id=cajero_id)
    except POSValidationError as err:
        db.session.rollback()
        return error_response(str(err), 422, "pos_validation_error")
    except POSPermissionError as err:
        db.session.rollback()
        return error_response(str(err), 403, "forbidden")

    # Recargamos con relaciones para la serialización.
    factura = db.session.execute(
        select(Factura)
        .options(
            selectinload(Factura.items),
            selectinload(Factura.pagos),
            selectinload(Factura.cliente),
        )
        .where(Factura.id == factura.id)
    ).scalar_one()

    return jsonify(_serialize_factura(factura)), 201


@bp.get("")
@roles_required("admin", "supervisor", "cajero", "contador")
def list_facturas():
    claims = get_jwt()
    rol = claims.get("rol")
    user_sucursal = claims.get("sucursal_id")

    sucursal_id = request.args.get("sucursal_id", type=int)
    tipo = request.args.get("tipo")
    cliente_id = request.args.get("cliente_id", type=int)
    fecha_desde = _parse_date(request.args.get("fecha_desde"))
    fecha_hasta = _parse_date(request.args.get("fecha_hasta"))

    stmt = select(Factura).options(
        selectinload(Factura.items),
        selectinload(Factura.pagos),
        selectinload(Factura.cliente),
    )

    # Cajero: sólo ve su sucursal.
    if rol == "cajero" and user_sucursal:
        stmt = stmt.where(Factura.sucursal_id == user_sucursal)
    elif sucursal_id:
        stmt = stmt.where(Factura.sucursal_id == sucursal_id)

    if tipo:
        try:
            tipo_enum = TipoComprobanteEnum(tipo)
            stmt = stmt.where(Factura.tipo == tipo_enum)
        except ValueError:
            return error_response(f"tipo inválido: {tipo}", 422, "validation_error")

    if cliente_id:
        stmt = stmt.where(Factura.cliente_id == cliente_id)
    if fecha_desde:
        stmt = stmt.where(Factura.fecha >= datetime.combine(fecha_desde, datetime.min.time()))
    if fecha_hasta:
        stmt = stmt.where(Factura.fecha <= datetime.combine(fecha_hasta, datetime.max.time()))

    stmt = stmt.order_by(Factura.fecha.desc(), Factura.id.desc())
    page, per_page = get_page_params()

    # Paginación manual para poder enriquecer cada item con cliente_resumen.
    from math import ceil

    from sqlalchemy import func

    total = db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        db.session.execute(stmt.offset((page - 1) * per_page).limit(per_page))
        .scalars()
        .all()
    )
    return jsonify(
        {
            "items": [_serialize_factura(f) for f in rows],
            "page": page,
            "per_page": per_page,
            "total": int(total),
            "pages": ceil(total / per_page) if per_page else 0,
        }
    )


@bp.get("/<int:factura_id>")
@roles_required("admin", "supervisor", "cajero", "contador")
def get_factura(factura_id: int):
    claims = get_jwt()
    rol = claims.get("rol")
    user_sucursal = claims.get("sucursal_id")

    factura = db.session.execute(
        select(Factura)
        .options(
            selectinload(Factura.items),
            selectinload(Factura.pagos),
            selectinload(Factura.cliente),
        )
        .where(Factura.id == factura_id)
    ).scalar_one_or_none()

    if factura is None:
        return error_response("factura no encontrada", 404, "not_found")

    if rol == "cajero" and user_sucursal and factura.sucursal_id != user_sucursal:
        return error_response("factura fuera de tu sucursal", 403, "forbidden_sucursal")

    return jsonify(_serialize_factura(factura))


@bp.post("/<int:factura_id>/anular")
@roles_required("admin", "supervisor")
def post_anular(factura_id: int):
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return error_response("token inválido", 401, "invalid_token")

    try:
        factura = anular_factura(db.session, factura_id, user_id=user_id)
    except POSValidationError as err:
        db.session.rollback()
        return error_response(str(err), 422, "pos_validation_error")

    factura = db.session.execute(
        select(Factura)
        .options(
            selectinload(Factura.items),
            selectinload(Factura.pagos),
            selectinload(Factura.cliente),
        )
        .where(Factura.id == factura.id)
    ).scalar_one()
    return jsonify(_serialize_factura(factura))
