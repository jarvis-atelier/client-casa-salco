"""CRUD de proveedores."""
from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.proveedor import Proveedor
from app.schemas.proveedor import ProveedorCreate, ProveedorOut, ProveedorUpdate
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

bp = Blueprint("proveedores", __name__, url_prefix="/api/v1/proveedores")


@bp.get("")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def list_proveedores():
    stmt = select(Proveedor).where(Proveedor.deleted_at.is_(None)).order_by(Proveedor.razon_social)
    rows = db.session.execute(stmt).scalars().all()
    return jsonify([ProveedorOut.model_validate(r).model_dump(mode="json") for r in rows])


@bp.post("")
@roles_required("admin", "supervisor")
def create_proveedor():
    try:
        payload = ProveedorCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    if db.session.query(Proveedor).filter(Proveedor.codigo == payload.codigo).first():
        return error_response("codigo duplicado", 409, "duplicate")
    prov = Proveedor(**payload.model_dump())
    db.session.add(prov)
    db.session.commit()
    return jsonify(ProveedorOut.model_validate(prov).model_dump(mode="json")), 201


@bp.get("/<int:prov_id>")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def get_proveedor(prov_id: int):
    prov = db.session.get(Proveedor, prov_id)
    if prov is None or prov.deleted_at is not None:
        return error_response("proveedor no encontrado", 404, "not_found")
    return jsonify(ProveedorOut.model_validate(prov).model_dump(mode="json"))


@bp.patch("/<int:prov_id>")
@roles_required("admin", "supervisor")
def update_proveedor(prov_id: int):
    prov = db.session.get(Proveedor, prov_id)
    if prov is None or prov.deleted_at is not None:
        return error_response("proveedor no encontrado", 404, "not_found")
    try:
        payload = ProveedorUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(prov, k, v)
    db.session.commit()
    return jsonify(ProveedorOut.model_validate(prov).model_dump(mode="json"))


@bp.delete("/<int:prov_id>")
@roles_required("admin")
def delete_proveedor(prov_id: int):
    prov = db.session.get(Proveedor, prov_id)
    if prov is None or prov.deleted_at is not None:
        return error_response("proveedor no encontrado", 404, "not_found")
    prov.deleted_at = datetime.now(UTC)
    prov.activo = False
    db.session.commit()
    return "", 204
