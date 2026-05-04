"""Endpoints OCR — upload de comprobantes, listado, confirmar, descartar.

Flujo:
    POST /api/v1/ocr/comprobante       (multipart) → extraer
    GET  /api/v1/ocr/comprobantes
    GET  /api/v1/ocr/comprobantes/:id
    GET  /api/v1/ocr/comprobantes/:id/imagen
    POST /api/v1/ocr/comprobantes/:id/confirmar
    POST /api/v1/ocr/comprobantes/:id/descartar
"""
from __future__ import annotations

from datetime import date
from math import ceil
from typing import Any

from flask import Blueprint, jsonify, request, send_file
from flask_jwt_extended import get_jwt, get_jwt_identity
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models.comprobante_ocr import ComprobanteOcr, EstadoOcrEnum
from app.schemas.ocr import (
    ComprobanteOcrOut,
    FacturaResumenOut,
    OcrConfirmarPayload,
    ProveedorMatchOut,
)
from app.services.ocr.service import (
    OcrServiceError,
    UPLOAD_DIR,
    confirmar as svc_confirmar,
    descartar as svc_descartar,
    upload_y_extraer,
)
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response
from app.utils.pagination import get_page_params

bp = Blueprint("ocr", __name__, url_prefix="/api/v1/ocr")


def _serialize(c: ComprobanteOcr) -> dict[str, Any]:
    out = ComprobanteOcrOut.model_validate(c).model_dump(mode="json")
    if c.proveedor_match is not None:
        out["proveedor_match"] = ProveedorMatchOut.model_validate(c.proveedor_match).model_dump(
            mode="json"
        )
    if c.factura_creada is not None:
        out["factura_creada"] = FacturaResumenOut.model_validate(c.factura_creada).model_dump(
            mode="json"
        )
    return out


def _reload(comprobante_id: int) -> ComprobanteOcr | None:
    return db.session.execute(
        select(ComprobanteOcr)
        .options(
            selectinload(ComprobanteOcr.proveedor_match),
            selectinload(ComprobanteOcr.factura_creada),
        )
        .where(ComprobanteOcr.id == comprobante_id)
    ).scalar_one_or_none()


@bp.post("/comprobante")
@roles_required("admin", "supervisor", "cajero")
def upload_comprobante():
    """Sube una imagen y dispara extracción OCR síncrona."""
    if "file" not in request.files:
        return error_response("falta archivo en form-data 'file'", 422, "missing_file")

    file = request.files["file"]
    content = file.read()
    mime = file.mimetype or "application/octet-stream"

    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return error_response("token inválido", 401, "invalid_token")

    claims = get_jwt()
    sucursal_id_form = request.form.get("sucursal_id", type=int)
    sucursal_id = sucursal_id_form or claims.get("sucursal_id")

    try:
        comprobante = upload_y_extraer(
            db.session,
            file_bytes=content,
            mime=mime,
            user_id=user_id,
            sucursal_id=sucursal_id,
        )
    except OcrServiceError as exc:
        db.session.rollback()
        return error_response(str(exc), 422, "ocr_validation_error")

    reloaded = _reload(comprobante.id)
    return jsonify(_serialize(reloaded or comprobante)), 201


@bp.get("/comprobantes")
@roles_required("admin", "supervisor", "cajero", "contador")
def list_comprobantes():
    estado = request.args.get("estado")
    claims = get_jwt()
    rol = claims.get("rol")

    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return error_response("token inválido", 401, "invalid_token")

    stmt = select(ComprobanteOcr).options(
        selectinload(ComprobanteOcr.proveedor_match),
        selectinload(ComprobanteOcr.factura_creada),
    )

    # Cajero solo ve los suyos.
    if rol == "cajero":
        stmt = stmt.where(ComprobanteOcr.uploaded_by_user_id == user_id)

    if estado:
        try:
            est = EstadoOcrEnum(estado)
            stmt = stmt.where(ComprobanteOcr.estado == est)
        except ValueError:
            return error_response(f"estado inválido: {estado}", 422, "validation_error")

    stmt = stmt.order_by(ComprobanteOcr.created_at.desc(), ComprobanteOcr.id.desc())
    page, per_page = get_page_params()

    total = db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = (
        db.session.execute(stmt.offset((page - 1) * per_page).limit(per_page))
        .scalars()
        .all()
    )
    return jsonify(
        {
            "items": [_serialize(c) for c in rows],
            "page": page,
            "per_page": per_page,
            "total": int(total),
            "pages": ceil(total / per_page) if per_page else 0,
        }
    )


@bp.get("/comprobantes/<int:comprobante_id>")
@roles_required("admin", "supervisor", "cajero", "contador")
def get_comprobante(comprobante_id: int):
    comprobante = _reload(comprobante_id)
    if comprobante is None:
        return error_response("comprobante no encontrado", 404, "not_found")

    claims = get_jwt()
    rol = claims.get("rol")
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return error_response("token inválido", 401, "invalid_token")

    if rol == "cajero" and comprobante.uploaded_by_user_id != user_id:
        return error_response(
            "no podés ver comprobantes de otros usuarios", 403, "forbidden"
        )

    return jsonify(_serialize(comprobante))


@bp.get("/comprobantes/<int:comprobante_id>/imagen")
@roles_required("admin", "supervisor", "cajero", "contador")
def get_imagen(comprobante_id: int):
    comprobante = db.session.get(ComprobanteOcr, comprobante_id)
    if comprobante is None:
        return error_response("comprobante no encontrado", 404, "not_found")

    claims = get_jwt()
    rol = claims.get("rol")
    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return error_response("token inválido", 401, "invalid_token")
    if rol == "cajero" and comprobante.uploaded_by_user_id != user_id:
        return error_response("forbidden", 403, "forbidden")

    target = UPLOAD_DIR / comprobante.archivo_path
    if not target.exists():
        return error_response("archivo no encontrado en disco", 404, "file_missing")

    return send_file(
        target,
        mimetype=comprobante.archivo_mime,
        as_attachment=False,
        download_name=f"ocr-{comprobante.id}{target.suffix}",
    )


@bp.post("/comprobantes/<int:comprobante_id>/confirmar")
@roles_required("admin", "supervisor")
def post_confirmar(comprobante_id: int):
    comprobante = db.session.get(ComprobanteOcr, comprobante_id)
    if comprobante is None:
        return error_response("comprobante no encontrado", 404, "not_found")

    try:
        payload = OcrConfirmarPayload.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )

    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return error_response("token inválido", 401, "invalid_token")

    items_dict: list[dict[str, Any]] = []
    for it in payload.items:
        items_dict.append(
            {
                "descripcion": it.descripcion,
                "cantidad": it.cantidad,
                "unidad": it.unidad,
                "precio_unitario": it.precio_unitario,
                "iva_porc": it.iva_porc,
                "descuento_porc": it.descuento_porc,
                "articulo_id": it.articulo_id,
                "crear_articulo_si_falta": it.crear_articulo_si_falta,
            }
        )

    fecha_override: date | None = payload.fecha_override

    try:
        svc_confirmar(
            db.session,
            comprobante,
            sucursal_id=payload.sucursal_id,
            items=items_dict,
            proveedor_id=payload.proveedor_id,
            numero_override=payload.numero_override,
            fecha_override=fecha_override,
            observacion=payload.observacion,
            user_id=user_id,
        )
    except OcrServiceError as exc:
        db.session.rollback()
        return error_response(str(exc), 422, "ocr_validation_error")

    reloaded = _reload(comprobante_id)
    return jsonify(_serialize(reloaded or comprobante))


@bp.post("/comprobantes/<int:comprobante_id>/descartar")
@roles_required("admin", "supervisor")
def post_descartar(comprobante_id: int):
    comprobante = db.session.get(ComprobanteOcr, comprobante_id)
    if comprobante is None:
        return error_response("comprobante no encontrado", 404, "not_found")
    try:
        svc_descartar(db.session, comprobante)
    except OcrServiceError as exc:
        db.session.rollback()
        return error_response(str(exc), 422, "ocr_validation_error")
    reloaded = _reload(comprobante_id)
    return jsonify(_serialize(reloaded or comprobante))
