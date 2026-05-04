"""CRUD de subrubros — anidados bajo rubro."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.categorias import Rubro, Subrubro
from app.schemas.categorias import SubrubroCreate, SubrubroOut, SubrubroUpdate
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

bp = Blueprint("subrubros", __name__, url_prefix="/api/v1")


@bp.get("/rubros/<int:rubro_id>/subrubros")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def list_subrubros(rubro_id: int):
    if db.session.get(Rubro, rubro_id) is None:
        return error_response("rubro no encontrado", 404, "not_found")
    rows = (
        db.session.execute(
            select(Subrubro)
            .where(Subrubro.rubro_id == rubro_id)
            .order_by(Subrubro.orden, Subrubro.codigo)
        )
        .scalars()
        .all()
    )
    return jsonify([SubrubroOut.model_validate(r).model_dump(mode="json") for r in rows])


@bp.post("/rubros/<int:rubro_id>/subrubros")
@roles_required("admin", "supervisor")
def create_subrubro(rubro_id: int):
    if db.session.get(Rubro, rubro_id) is None:
        return error_response("rubro no encontrado", 404, "not_found")
    try:
        payload = SubrubroCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    sub = Subrubro(rubro_id=rubro_id, **payload.model_dump())
    db.session.add(sub)
    db.session.commit()
    return jsonify(SubrubroOut.model_validate(sub).model_dump(mode="json")), 201


@bp.patch("/subrubros/<int:sub_id>")
@roles_required("admin", "supervisor")
def update_subrubro(sub_id: int):
    sub = db.session.get(Subrubro, sub_id)
    if sub is None:
        return error_response("subrubro no encontrado", 404, "not_found")
    try:
        payload = SubrubroUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(sub, k, v)
    db.session.commit()
    return jsonify(SubrubroOut.model_validate(sub).model_dump(mode="json"))


@bp.delete("/subrubros/<int:sub_id>")
@roles_required("admin")
def delete_subrubro(sub_id: int):
    sub = db.session.get(Subrubro, sub_id)
    if sub is None:
        return error_response("subrubro no encontrado", 404, "not_found")
    db.session.delete(sub)
    db.session.commit()
    return "", 204
