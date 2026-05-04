"""Endpoints para el módulo de alertas (admin only)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.models.alerta import (
    Alerta,
    EstadoAlertaEnum,
    SeveridadEnum,
    TipoAlertaEnum,
)
from app.schemas.alerta import (
    AlertaDetalleOut,
    AlertaOut,
    AlertaPatch,
    AlertaResumen,
    AlertaRunResult,
)
from app.services.alerts.runner import run_all_detectors
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response
from app.utils.pagination import get_page_params, paginate_query

bp = Blueprint("alertas", __name__, url_prefix="/api/v1/alertas")


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# GET /alertas — listado paginado con filtros
# ---------------------------------------------------------------------------


@bp.get("")
@roles_required("admin")
def list_alertas():
    tipo = request.args.get("tipo")
    severidad = request.args.get("severidad")
    estado = request.args.get("estado")
    fecha_desde = _parse_date(request.args.get("fecha_desde"))
    fecha_hasta = _parse_date(request.args.get("fecha_hasta"))
    incluir_cerradas = request.args.get("incluir_cerradas", "0") in ("1", "true")

    stmt = select(Alerta)

    if tipo:
        try:
            stmt = stmt.where(Alerta.tipo == TipoAlertaEnum(tipo))
        except ValueError:
            return error_response(f"tipo inválido: {tipo}", 422, "validation_error")

    if severidad:
        try:
            stmt = stmt.where(Alerta.severidad == SeveridadEnum(severidad))
        except ValueError:
            return error_response(
                f"severidad inválida: {severidad}", 422, "validation_error"
            )

    if estado:
        try:
            stmt = stmt.where(Alerta.estado == EstadoAlertaEnum(estado))
        except ValueError:
            return error_response(
                f"estado inválido: {estado}", 422, "validation_error"
            )
    elif not incluir_cerradas:
        # Default: oculta descartadas y resueltas
        stmt = stmt.where(
            Alerta.estado.in_(
                [
                    EstadoAlertaEnum.nueva,
                    EstadoAlertaEnum.en_revision,
                    EstadoAlertaEnum.confirmada,
                ]
            )
        )

    if fecha_desde:
        stmt = stmt.where(
            Alerta.detected_at >= datetime.combine(fecha_desde, datetime.min.time())
        )
    if fecha_hasta:
        stmt = stmt.where(
            Alerta.detected_at <= datetime.combine(fecha_hasta, datetime.max.time())
        )

    # Orden: severidad crítica primero, luego fecha desc
    severidad_orden = {
        SeveridadEnum.critica: 0,
        SeveridadEnum.alta: 1,
        SeveridadEnum.media: 2,
        SeveridadEnum.baja: 3,
    }
    # Como Enum no se puede ordenar por valor, ordenamos por detected_at desc
    stmt = stmt.order_by(Alerta.detected_at.desc(), Alerta.id.desc())

    page, per_page = get_page_params()
    return jsonify(paginate_query(stmt, AlertaOut, page, per_page))


# ---------------------------------------------------------------------------
# GET /alertas/resumen — para el badge del sidebar
# ---------------------------------------------------------------------------


@bp.get("/resumen")
@roles_required("admin")
def get_resumen():
    nuevas = db.session.scalar(
        select(func.count(Alerta.id)).where(Alerta.estado == EstadoAlertaEnum.nueva)
    ) or 0
    en_revision = db.session.scalar(
        select(func.count(Alerta.id)).where(
            Alerta.estado == EstadoAlertaEnum.en_revision
        )
    ) or 0
    criticas = db.session.scalar(
        select(func.count(Alerta.id)).where(
            Alerta.severidad == SeveridadEnum.critica,
            Alerta.estado.in_(
                [
                    EstadoAlertaEnum.nueva,
                    EstadoAlertaEnum.en_revision,
                    EstadoAlertaEnum.confirmada,
                ]
            ),
        )
    ) or 0
    desde_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    ultimas_24h = db.session.scalar(
        select(func.count(Alerta.id)).where(Alerta.detected_at >= desde_24h)
    ) or 0
    total_abiertas = db.session.scalar(
        select(func.count(Alerta.id)).where(
            Alerta.estado.in_(
                [
                    EstadoAlertaEnum.nueva,
                    EstadoAlertaEnum.en_revision,
                    EstadoAlertaEnum.confirmada,
                ]
            )
        )
    ) or 0

    return jsonify(
        AlertaResumen(
            nuevas=nuevas,
            en_revision=en_revision,
            criticas=criticas,
            ultimas_24h=ultimas_24h,
            total_abiertas=total_abiertas,
        ).model_dump()
    )


# ---------------------------------------------------------------------------
# GET /alertas/<id> — detalle enriquecido
# ---------------------------------------------------------------------------


@bp.get("/<int:alerta_id>")
@roles_required("admin")
def get_alerta(alerta_id: int):
    alerta = db.session.execute(
        select(Alerta)
        .options(
            selectinload(Alerta.factura),
            selectinload(Alerta.user_relacionado),
            selectinload(Alerta.proveedor),
            selectinload(Alerta.sucursal),
        )
        .where(Alerta.id == alerta_id)
    ).scalar_one_or_none()
    if alerta is None:
        return error_response("alerta no encontrada", 404, "not_found")

    base = AlertaOut.model_validate(alerta).model_dump(mode="json")

    if alerta.factura is not None:
        base["factura"] = {
            "id": alerta.factura.id,
            "tipo": alerta.factura.tipo.value,
            "numero": alerta.factura.numero,
            "punto_venta": alerta.factura.punto_venta,
            "fecha": alerta.factura.fecha.isoformat(),
            "total": str(alerta.factura.total),
            "estado": alerta.factura.estado.value,
            "sucursal_id": alerta.factura.sucursal_id,
            "cliente_id": alerta.factura.cliente_id,
            "cajero_id": alerta.factura.cajero_id,
        }
    else:
        base["factura"] = None

    if alerta.user_relacionado is not None:
        u = alerta.user_relacionado
        base["user_relacionado"] = {
            "id": u.id,
            "email": u.email,
            "nombre": u.nombre,
            "rol": u.rol.value if u.rol else None,
            "sucursal_id": u.sucursal_id,
        }
    else:
        base["user_relacionado"] = None

    if alerta.proveedor is not None:
        p = alerta.proveedor
        base["proveedor"] = {
            "id": p.id,
            "codigo": p.codigo,
            "razon_social": p.razon_social,
            "cuit": p.cuit,
        }
    else:
        base["proveedor"] = None

    if alerta.sucursal is not None:
        s = alerta.sucursal
        base["sucursal"] = {
            "id": s.id,
            "codigo": s.codigo,
            "nombre": s.nombre,
        }
    else:
        base["sucursal"] = None

    return jsonify(base)


# ---------------------------------------------------------------------------
# POST /alertas/run — corre todos los detectores
# ---------------------------------------------------------------------------


@bp.post("/run")
@roles_required("admin")
def run_detectors():
    ventana_dias = request.args.get("ventana_dias", default=90, type=int)
    ventana_dias = max(1, min(ventana_dias, 365))

    result = run_all_detectors(db.session, ventana_dias=ventana_dias)
    return jsonify(AlertaRunResult(**result).model_dump())


# ---------------------------------------------------------------------------
# PATCH /alertas/<id> — cambiar estado / nota
# ---------------------------------------------------------------------------


@bp.patch("/<int:alerta_id>")
@roles_required("admin")
def patch_alerta(alerta_id: int):
    try:
        payload = AlertaPatch.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )

    alerta = db.session.get(Alerta, alerta_id)
    if alerta is None:
        return error_response("alerta no encontrada", 404, "not_found")

    if payload.estado is not None:
        alerta.estado = payload.estado
        # Marcar resuelto si pasa a estado terminal
        if payload.estado in (
            EstadoAlertaEnum.descartada,
            EstadoAlertaEnum.resuelta,
        ):
            alerta.resolved_at = datetime.now(timezone.utc)
            try:
                alerta.resolved_by_user_id = int(get_jwt_identity())
            except (TypeError, ValueError):
                pass
        else:
            alerta.resolved_at = None
            alerta.resolved_by_user_id = None

    if payload.nota_resolucion is not None:
        alerta.nota_resolucion = payload.nota_resolucion

    db.session.commit()
    return jsonify(AlertaOut.model_validate(alerta).model_dump(mode="json"))


# ---------------------------------------------------------------------------
# DELETE /alertas/<id> — sólo si está descartada o resuelta
# ---------------------------------------------------------------------------


@bp.delete("/<int:alerta_id>")
@roles_required("admin")
def delete_alerta(alerta_id: int):
    alerta = db.session.get(Alerta, alerta_id)
    if alerta is None:
        return error_response("alerta no encontrada", 404, "not_found")
    if alerta.estado not in (EstadoAlertaEnum.descartada, EstadoAlertaEnum.resuelta):
        return error_response(
            "sólo se pueden eliminar alertas descartadas o resueltas",
            422,
            "invalid_state",
        )
    db.session.delete(alerta)
    db.session.commit()
    return jsonify(deleted=True, id=alerta_id)
