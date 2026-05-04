"""CRUD de marcas."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.categorias import Marca
from app.schemas.categorias import MarcaCreate, MarcaOut, MarcaUpdate
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

bp = Blueprint("marcas", __name__, url_prefix="/api/v1/marcas")


@bp.get("")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def list_marcas():
    rows = db.session.execute(select(Marca).order_by(Marca.nombre)).scalars().all()
    return jsonify([MarcaOut.model_validate(r).model_dump(mode="json") for r in rows])


@bp.post("")
@roles_required("admin", "supervisor")
def create_marca():
    try:
        payload = MarcaCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    if db.session.query(Marca).filter(Marca.nombre == payload.nombre).first():
        return error_response("marca duplicada", 409, "duplicate")
    marca = Marca(**payload.model_dump())
    db.session.add(marca)
    db.session.commit()
    return jsonify(MarcaOut.model_validate(marca).model_dump(mode="json")), 201


@bp.get("/<int:marca_id>")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def get_marca(marca_id: int):
    marca = db.session.get(Marca, marca_id)
    if marca is None:
        return error_response("marca no encontrada", 404, "not_found")
    return jsonify(MarcaOut.model_validate(marca).model_dump(mode="json"))


@bp.patch("/<int:marca_id>")
@roles_required("admin", "supervisor")
def update_marca(marca_id: int):
    marca = db.session.get(Marca, marca_id)
    if marca is None:
        return error_response("marca no encontrada", 404, "not_found")
    try:
        payload = MarcaUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(marca, k, v)
    db.session.commit()
    return jsonify(MarcaOut.model_validate(marca).model_dump(mode="json"))


@bp.delete("/<int:marca_id>")
@roles_required("admin")
def delete_marca(marca_id: int):
    marca = db.session.get(Marca, marca_id)
    if marca is None:
        return error_response("marca no encontrada", 404, "not_found")
    db.session.delete(marca)
    db.session.commit()
    return "", 204
