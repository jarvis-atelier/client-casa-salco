"""CRUD de clientes + búsqueda."""
from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import or_, select

from app.extensions import db
from app.models.cliente import Cliente
from app.schemas.cliente import ClienteCreate, ClienteOut, ClienteUpdate
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response
from app.utils.pagination import get_page_params, paginate_query

bp = Blueprint("clientes", __name__, url_prefix="/api/v1/clientes")


@bp.get("")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def list_clientes():
    q = (request.args.get("q") or "").strip()
    stmt = select(Cliente).where(Cliente.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Cliente.codigo.ilike(like),
                Cliente.razon_social.ilike(like),
                Cliente.cuit.ilike(like),
            )
        )
    stmt = stmt.order_by(Cliente.razon_social)
    page, per_page = get_page_params()
    return jsonify(paginate_query(stmt, ClienteOut, page, per_page))


@bp.post("")
@roles_required("admin", "supervisor")
def create_cliente():
    try:
        payload = ClienteCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    if db.session.query(Cliente).filter(Cliente.codigo == payload.codigo).first():
        return error_response("codigo duplicado", 409, "duplicate")
    cli = Cliente(**payload.model_dump())
    db.session.add(cli)
    db.session.commit()
    return jsonify(ClienteOut.model_validate(cli).model_dump(mode="json")), 201


@bp.get("/<int:cli_id>")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def get_cliente(cli_id: int):
    cli = db.session.get(Cliente, cli_id)
    if cli is None or cli.deleted_at is not None:
        return error_response("cliente no encontrado", 404, "not_found")
    return jsonify(ClienteOut.model_validate(cli).model_dump(mode="json"))


@bp.patch("/<int:cli_id>")
@roles_required("admin", "supervisor")
def update_cliente(cli_id: int):
    cli = db.session.get(Cliente, cli_id)
    if cli is None or cli.deleted_at is not None:
        return error_response("cliente no encontrado", 404, "not_found")
    try:
        payload = ClienteUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cli, k, v)
    db.session.commit()
    return jsonify(ClienteOut.model_validate(cli).model_dump(mode="json"))


@bp.delete("/<int:cli_id>")
@roles_required("admin")
def delete_cliente(cli_id: int):
    cli = db.session.get(Cliente, cli_id)
    if cli is None or cli.deleted_at is not None:
        return error_response("cliente no encontrado", 404, "not_found")
    cli.deleted_at = datetime.now(UTC)
    cli.activo = False
    db.session.commit()
    return "", 204
