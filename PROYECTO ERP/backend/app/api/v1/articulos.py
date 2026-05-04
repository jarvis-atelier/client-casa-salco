"""CRUD de artículos + búsqueda paginada + listado de precios."""
from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from pydantic import ValidationError
from sqlalchemy import or_, select

from app.extensions import db
from app.models.articulo import Articulo
from app.models.precio import PrecioSucursal
from app.schemas.articulo import ArticuloCreate, ArticuloOut, ArticuloUpdate
from app.schemas.precio import PrecioSucursalOut
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response
from app.utils.pagination import get_page_params, paginate_query

bp = Blueprint("articulos", __name__, url_prefix="/api/v1/articulos")


@bp.get("")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def list_articulos():
    q = (request.args.get("q") or "").strip()
    familia_id = request.args.get("familia_id", type=int)
    rubro_id = request.args.get("rubro_id", type=int)
    subrubro_id = request.args.get("subrubro_id", type=int)
    marca_id = request.args.get("marca_id", type=int)
    proveedor_id = request.args.get("proveedor_id", type=int)
    solo_activos = request.args.get("solo_activos", "1") == "1"

    stmt = select(Articulo).where(Articulo.deleted_at.is_(None))
    if solo_activos:
        stmt = stmt.where(Articulo.activo.is_(True))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Articulo.codigo.ilike(like),
                Articulo.codigo_barras.ilike(like),
                Articulo.descripcion.ilike(like),
            )
        )
    if familia_id:
        stmt = stmt.where(Articulo.familia_id == familia_id)
    if rubro_id:
        stmt = stmt.where(Articulo.rubro_id == rubro_id)
    if subrubro_id:
        stmt = stmt.where(Articulo.subrubro_id == subrubro_id)
    if marca_id:
        stmt = stmt.where(Articulo.marca_id == marca_id)
    if proveedor_id:
        stmt = stmt.where(Articulo.proveedor_principal_id == proveedor_id)

    stmt = stmt.order_by(Articulo.descripcion)
    page, per_page = get_page_params()
    return jsonify(paginate_query(stmt, ArticuloOut, page, per_page))


@bp.post("")
@roles_required("admin", "supervisor")
def create_articulo():
    try:
        payload = ArticuloCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    if db.session.query(Articulo).filter(Articulo.codigo == payload.codigo).first():
        return error_response("codigo duplicado", 409, "duplicate")
    art = Articulo(**payload.model_dump())
    db.session.add(art)
    db.session.commit()
    return jsonify(ArticuloOut.model_validate(art).model_dump(mode="json")), 201


@bp.get("/<int:art_id>")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def get_articulo(art_id: int):
    art = db.session.get(Articulo, art_id)
    if art is None or art.deleted_at is not None:
        return error_response("articulo no encontrado", 404, "not_found")
    return jsonify(ArticuloOut.model_validate(art).model_dump(mode="json"))


@bp.patch("/<int:art_id>")
@roles_required("admin", "supervisor")
def update_articulo(art_id: int):
    art = db.session.get(Articulo, art_id)
    if art is None or art.deleted_at is not None:
        return error_response("articulo no encontrado", 404, "not_found")
    try:
        payload = ArticuloUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(art, k, v)
    db.session.commit()
    return jsonify(ArticuloOut.model_validate(art).model_dump(mode="json"))


@bp.delete("/<int:art_id>")
@roles_required("admin")
def delete_articulo(art_id: int):
    art = db.session.get(Articulo, art_id)
    if art is None or art.deleted_at is not None:
        return error_response("articulo no encontrado", 404, "not_found")
    art.deleted_at = datetime.now(UTC)
    art.activo = False
    db.session.commit()
    return "", 204


@bp.get("/<int:art_id>/precios")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def get_precios_articulo(art_id: int):
    art = db.session.get(Articulo, art_id)
    if art is None or art.deleted_at is not None:
        return error_response("articulo no encontrado", 404, "not_found")
    stmt = (
        select(PrecioSucursal)
        .where(PrecioSucursal.articulo_id == art_id, PrecioSucursal.activo.is_(True))
        .order_by(PrecioSucursal.sucursal_id)
    )
    rows = db.session.execute(stmt).scalars().all()
    return jsonify([PrecioSucursalOut.model_validate(r).model_dump(mode="json") for r in rows])
