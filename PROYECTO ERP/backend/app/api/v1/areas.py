"""CRUD de áreas — anidado bajo sucursal."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.sucursal import Area, Sucursal
from app.schemas.sucursal import AreaCreate, AreaOut, AreaUpdate
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

bp = Blueprint("areas", __name__, url_prefix="/api/v1")


@bp.get("/sucursales/<int:suc_id>/areas")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def list_areas(suc_id: int):
    if db.session.get(Sucursal, suc_id) is None:
        return error_response("sucursal no encontrada", 404, "not_found")
    rows = (
        db.session.execute(
            select(Area).where(Area.sucursal_id == suc_id).order_by(Area.orden, Area.codigo)
        )
        .scalars()
        .all()
    )
    return jsonify([AreaOut.model_validate(r).model_dump(mode="json") for r in rows])


@bp.post("/sucursales/<int:suc_id>/areas")
@roles_required("admin", "supervisor")
def create_area(suc_id: int):
    if db.session.get(Sucursal, suc_id) is None:
        return error_response("sucursal no encontrada", 404, "not_found")
    try:
        payload = AreaCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    area = Area(sucursal_id=suc_id, **payload.model_dump())
    db.session.add(area)
    db.session.commit()
    return jsonify(AreaOut.model_validate(area).model_dump(mode="json")), 201


@bp.patch("/areas/<int:area_id>")
@roles_required("admin", "supervisor")
def update_area(area_id: int):
    area = db.session.get(Area, area_id)
    if area is None:
        return error_response("area no encontrada", 404, "not_found")
    try:
        payload = AreaUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(area, k, v)
    db.session.commit()
    return jsonify(AreaOut.model_validate(area).model_dump(mode="json"))


@bp.delete("/areas/<int:area_id>")
@roles_required("admin")
def delete_area(area_id: int):
    area = db.session.get(Area, area_id)
    if area is None:
        return error_response("area no encontrada", 404, "not_found")
    db.session.delete(area)
    db.session.commit()
    return "", 204
