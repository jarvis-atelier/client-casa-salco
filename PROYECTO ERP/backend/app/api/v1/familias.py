"""CRUD de familias."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.categorias import Familia
from app.schemas.categorias import FamiliaCreate, FamiliaOut, FamiliaUpdate
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

bp = Blueprint("familias", __name__, url_prefix="/api/v1/familias")


@bp.get("")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def list_familias():
    stmt = select(Familia).order_by(Familia.orden, Familia.codigo)
    rows = db.session.execute(stmt).scalars().all()
    return jsonify([FamiliaOut.model_validate(r).model_dump(mode="json") for r in rows])


@bp.post("")
@roles_required("admin", "supervisor")
def create_familia():
    try:
        payload = FamiliaCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    if db.session.query(Familia).filter(Familia.codigo == payload.codigo).first():
        return error_response("codigo duplicado", 409, "duplicate")
    fam = Familia(**payload.model_dump())
    db.session.add(fam)
    db.session.commit()
    return jsonify(FamiliaOut.model_validate(fam).model_dump(mode="json")), 201


@bp.get("/<int:fam_id>")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def get_familia(fam_id: int):
    fam = db.session.get(Familia, fam_id)
    if fam is None:
        return error_response("familia no encontrada", 404, "not_found")
    return jsonify(FamiliaOut.model_validate(fam).model_dump(mode="json"))


@bp.patch("/<int:fam_id>")
@roles_required("admin", "supervisor")
def update_familia(fam_id: int):
    fam = db.session.get(Familia, fam_id)
    if fam is None:
        return error_response("familia no encontrada", 404, "not_found")
    try:
        payload = FamiliaUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(fam, k, v)
    db.session.commit()
    return jsonify(FamiliaOut.model_validate(fam).model_dump(mode="json"))


@bp.delete("/<int:fam_id>")
@roles_required("admin")
def delete_familia(fam_id: int):
    fam = db.session.get(Familia, fam_id)
    if fam is None:
        return error_response("familia no encontrada", 404, "not_found")
    db.session.delete(fam)
    db.session.commit()
    return "", 204
