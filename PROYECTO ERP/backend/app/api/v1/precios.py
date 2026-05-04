"""Endpoints de precios — listado por artículo + actualización multi-sucursal."""
from __future__ import annotations

from decimal import Decimal

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from pydantic import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.articulo import Articulo
from app.models.precio import PrecioSucursal
from app.models.sucursal import Sucursal
from app.schemas.precio import (
    PrecioListadoItem,
    PrecioUpdateRequest,
    SucursalRef,
)
from app.services.price_sync import actualizar_precios, sucursales_activas_ids
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

bp = Blueprint("precios", __name__, url_prefix="/api/v1/precios")


@bp.get("")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def list_precios_por_articulo():
    """Lista precios vigentes por artículo con referencia a la sucursal.

    Query params:
        articulo_id (int, requerido)

    Responde un array con un item por sucursal activa que tenga precio vigente:
        [{"sucursal": {id, codigo, nombre}, "precio": "450.0000", "vigente_desde": "..."}, ...]
    """
    articulo_id = request.args.get("articulo_id", type=int)
    if not articulo_id:
        return error_response(
            "articulo_id es requerido", 422, "missing_parameter"
        )

    articulo = db.session.get(Articulo, articulo_id)
    if articulo is None or articulo.deleted_at is not None:
        return error_response("articulo no encontrado", 404, "not_found")

    stmt = (
        select(PrecioSucursal, Sucursal)
        .join(Sucursal, Sucursal.id == PrecioSucursal.sucursal_id)
        .where(
            PrecioSucursal.articulo_id == articulo_id,
            PrecioSucursal.activo.is_(True),
            Sucursal.deleted_at.is_(None),
        )
        .order_by(Sucursal.id)
    )
    rows = db.session.execute(stmt).all()

    items = [
        PrecioListadoItem(
            sucursal=SucursalRef.model_validate(suc),
            precio=str(precio.precio),
            vigente_desde=precio.vigente_desde,
        ).model_dump(mode="json")
        for precio, suc in rows
    ]
    return jsonify(items)


@bp.post("/actualizar")
@roles_required("admin", "supervisor")
def actualizar():
    try:
        payload = PrecioUpdateRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )

    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        user_id = None

    # Expandir a la lista final de (sucursal_id, precio)
    updates: list[tuple[int, Decimal]] = []
    if payload.aplicar_a_todas:
        assert payload.precio is not None  # validado en el schema
        for sid in sucursales_activas_ids():
            updates.append((sid, payload.precio))
        if not updates:
            return error_response(
                "no hay sucursales activas a las que aplicar el precio",
                409,
                "no_active_sucursales",
            )
    else:
        assert payload.cambios is not None  # validado en el schema
        updates = [(c.sucursal_id, c.precio) for c in payload.cambios]

    try:
        resumen = actualizar_precios(
            articulo_id=payload.articulo_id,
            updates=updates,
            user_id=user_id,
            motivo=payload.motivo,
        )
    except ValueError as err:
        return error_response(str(err), 404, "not_found")

    return jsonify(
        {
            "articulo_id": payload.articulo_id,
            "actualizados": len(resumen),
            "items": resumen,
        }
    )
