"""CRUD de sucursales."""
from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.sucursal import Sucursal
from app.schemas.sucursal import SucursalCreate, SucursalOut, SucursalUpdate
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

bp = Blueprint("sucursales", __name__, url_prefix="/api/v1/sucursales")


@bp.get("")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def list_sucursales():
    include_deleted = request.args.get("include_deleted") == "1"
    stmt = select(Sucursal)
    if not include_deleted:
        stmt = stmt.where(Sucursal.deleted_at.is_(None))
    rows = db.session.execute(stmt.order_by(Sucursal.codigo)).scalars().all()
    return jsonify([SucursalOut.model_validate(r).model_dump(mode="json") for r in rows])


@bp.post("")
@roles_required("admin", "supervisor")
def create_sucursal():
    try:
        payload = SucursalCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    if db.session.query(Sucursal).filter(Sucursal.codigo == payload.codigo).first():
        return error_response("codigo de sucursal duplicado", 409, "duplicate")

    suc = Sucursal(**payload.model_dump())
    db.session.add(suc)
    db.session.commit()
    return jsonify(SucursalOut.model_validate(suc).model_dump(mode="json")), 201


@bp.get("/<int:suc_id>")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def get_sucursal(suc_id: int):
    suc = db.session.get(Sucursal, suc_id)
    if suc is None or suc.deleted_at is not None:
        return error_response("sucursal no encontrada", 404, "not_found")
    return jsonify(SucursalOut.model_validate(suc).model_dump(mode="json"))


@bp.patch("/<int:suc_id>")
@roles_required("admin", "supervisor")
def update_sucursal(suc_id: int):
    suc = db.session.get(Sucursal, suc_id)
    if suc is None or suc.deleted_at is not None:
        return error_response("sucursal no encontrada", 404, "not_found")
    try:
        payload = SucursalUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(suc, k, v)
    db.session.commit()
    return jsonify(SucursalOut.model_validate(suc).model_dump(mode="json"))


@bp.delete("/<int:suc_id>")
@roles_required("admin")
def delete_sucursal(suc_id: int):
    suc = db.session.get(Sucursal, suc_id)
    if suc is None or suc.deleted_at is not None:
        return error_response("sucursal no encontrada", 404, "not_found")
    suc.deleted_at = datetime.now(UTC)
    suc.activa = False
    db.session.commit()
    return "", 204
