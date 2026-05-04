"""CRUD de rubros — anidados bajo familia."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.categorias import Familia, Rubro
from app.schemas.categorias import RubroCreate, RubroOut, RubroUpdate
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

bp = Blueprint("rubros", __name__, url_prefix="/api/v1")


@bp.get("/familias/<int:fam_id>/rubros")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def list_rubros(fam_id: int):
    if db.session.get(Familia, fam_id) is None:
        return error_response("familia no encontrada", 404, "not_found")
    rows = (
        db.session.execute(
            select(Rubro).where(Rubro.familia_id == fam_id).order_by(Rubro.orden, Rubro.codigo)
        )
        .scalars()
        .all()
    )
    return jsonify([RubroOut.model_validate(r).model_dump(mode="json") for r in rows])


@bp.post("/familias/<int:fam_id>/rubros")
@roles_required("admin", "supervisor")
def create_rubro(fam_id: int):
    if db.session.get(Familia, fam_id) is None:
        return error_response("familia no encontrada", 404, "not_found")
    try:
        payload = RubroCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    rubro = Rubro(familia_id=fam_id, **payload.model_dump())
    db.session.add(rubro)
    db.session.commit()
    return jsonify(RubroOut.model_validate(rubro).model_dump(mode="json")), 201


@bp.patch("/rubros/<int:rubro_id>")
@roles_required("admin", "supervisor")
def update_rubro(rubro_id: int):
    rubro = db.session.get(Rubro, rubro_id)
    if rubro is None:
        return error_response("rubro no encontrado", 404, "not_found")
    try:
        payload = RubroUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(rubro, k, v)
    db.session.commit()
    return jsonify(RubroOut.model_validate(rubro).model_dump(mode="json"))


@bp.delete("/rubros/<int:rubro_id>")
@roles_required("admin")
def delete_rubro(rubro_id: int):
    rubro = db.session.get(Rubro, rubro_id)
    if rubro is None:
        return error_response("rubro no encontrado", 404, "not_found")
    db.session.delete(rubro)
    db.session.commit()
    return "", 204
