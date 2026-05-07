"""Endpoints de stock — consulta por artículo + ajuste manual.

Opción C — stock inteligente:
- GET devuelve los campos efectivos (efectivo_minimo, efectivo_maximo,
  efectivo_reorden, efectivo_lead_time, estado_reposicion) además de los
  overrides puntuales de sucursal.
- POST /ajuste acepta opcionalmente min/max/reorden/lead_time para
  setearlos en el row de sucursal (override) en el mismo request del ajuste
  de cantidad. Para limpiar un override, pasar `unset_<campo>=true`.
"""
from __future__ import annotations

from datetime import UTC, datetime

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from pydantic import ValidationError
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models.articulo import Articulo
from app.models.resumen import MovimientoCaja, TipoMovimientoEnum
from app.models.stock import StockSucursal
from app.models.sucursal import Sucursal
from app.schemas.stock import StockAjusteRequest, StockResumen, StockSucursalOut
from app.services import stock_service
from app.services.analytics.sugerencias_reposicion import (
    LEAD_TIME_DEFAULT_DIAS,
    calcular_stock_optimo,
)
from app.services.analytics.velocidad_venta import calcular_velocidad_venta
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response
from app.utils.pagination import get_page_params, paginate_query

bp = Blueprint("stock", __name__, url_prefix="/api/v1/stock")


def _serialize(row: StockSucursal) -> dict:
    """Serializa con efectivos resueltos."""
    return StockSucursalOut.model_validate(row).model_dump(mode="json")


_ESTADOS_VALIDOS = {
    "agotado",
    "critico",
    "reorden",
    "sobrestock",
    "ok",
    "bajo_minimo",  # alias compuesto: agotado + critico
}


def _efectivos():
    """Expresiones SQL que reproducen la property `efectivo_*` del modelo:
    override de sucursal o, si NULL, default del articulo."""
    e_min = func.coalesce(StockSucursal.stock_minimo, Articulo.stock_minimo_default)
    e_reor = func.coalesce(StockSucursal.punto_reorden, Articulo.punto_reorden_default)
    e_max = func.coalesce(StockSucursal.stock_maximo, Articulo.stock_maximo_default)
    return e_min, e_reor, e_max


def _estado_filter(estado: str):
    """Devuelve la cláusula SQL para filtrar por estado_reposicion.

    Reproduce el if-elif de StockSucursal.estado_reposicion. Devuelve None si
    el estado es inválido.
    """
    if estado not in _ESTADOS_VALIDOS:
        return None
    e_min, e_reor, e_max = _efectivos()
    cant = StockSucursal.cantidad
    if estado == "agotado":
        return cant <= 0
    no_es_critico = or_(e_min.is_(None), cant > e_min)
    no_es_reorden = or_(e_reor.is_(None), cant > e_reor)
    if estado == "critico":
        return and_(cant > 0, e_min.is_not(None), cant <= e_min)
    if estado == "bajo_minimo":
        return or_(
            cant <= 0,
            and_(cant > 0, e_min.is_not(None), cant <= e_min),
        )
    if estado == "reorden":
        return and_(cant > 0, no_es_critico, e_reor.is_not(None), cant <= e_reor)
    if estado == "sobrestock":
        return and_(
            cant > 0,
            no_es_critico,
            no_es_reorden,
            e_max.is_not(None),
            cant > e_max,
        )
    # ok
    return and_(
        cant > 0,
        no_es_critico,
        no_es_reorden,
        or_(e_max.is_(None), cant <= e_max),
    )


@bp.get("")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def list_stock():
    articulo_id = request.args.get("articulo_id", type=int)
    sucursal_id = request.args.get("sucursal_id", type=int)
    q = (request.args.get("q") or "").strip()
    estado = (request.args.get("estado") or "").strip().lower() or None

    if not articulo_id and not sucursal_id:
        return error_response(
            "articulo_id o sucursal_id requerido", 422, "missing_parameter"
        )

    stmt = select(StockSucursal).options(
        joinedload(StockSucursal.articulo),
        joinedload(StockSucursal.sucursal),
    )
    if articulo_id:
        stmt = stmt.where(StockSucursal.articulo_id == articulo_id)
    if sucursal_id:
        stmt = stmt.where(StockSucursal.sucursal_id == sucursal_id)

    # Filtros que requieren JOIN con Articulo.
    if q or estado:
        stmt = stmt.join(Articulo, Articulo.id == StockSucursal.articulo_id)
        if q:
            like = f"%{q}%"
            stmt = stmt.where(
                or_(Articulo.codigo.ilike(like), Articulo.descripcion.ilike(like))
            )
        if estado:
            cond = _estado_filter(estado)
            if cond is None:
                return error_response(
                    f"estado inválido: {estado}", 422, "invalid_param"
                )
            stmt = stmt.where(cond)

    stmt = stmt.order_by(StockSucursal.sucursal_id, StockSucursal.articulo_id)

    # Si filtran por articulo_id (resultado chico, esperan lista cruda)
    # conserva el shape histórico para no romper consumidores.
    if articulo_id and not sucursal_id:
        rows = db.session.execute(stmt).scalars().unique().all()
        return jsonify([_serialize(r) for r in rows])

    page, per_page = get_page_params(default_per_page=50, max_per_page=500)
    return jsonify(paginate_query(stmt, StockSucursalOut, page, per_page))


@bp.get("/resumen")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def stock_resumen():
    sucursal_id = request.args.get("sucursal_id", type=int)
    if not sucursal_id:
        return error_response("sucursal_id requerido", 422, "missing_parameter")

    e_min, e_reor, e_max = _efectivos()
    cant = StockSucursal.cantidad

    # Cuenta cada estado en una sola query con SUM(CASE WHEN).
    estado_case = case(
        (cant <= 0, "agotado"),
        (and_(e_min.is_not(None), cant <= e_min), "critico"),
        (and_(e_reor.is_not(None), cant <= e_reor), "reorden"),
        (and_(e_max.is_not(None), cant > e_max), "sobrestock"),
        else_="ok",
    )

    stmt = (
        select(estado_case.label("estado"), func.count().label("n"))
        .select_from(StockSucursal)
        .join(Articulo, Articulo.id == StockSucursal.articulo_id)
        .where(StockSucursal.sucursal_id == sucursal_id)
        .group_by(estado_case)
    )
    rows = db.session.execute(stmt).all()
    counts = {estado: 0 for estado in _ESTADOS_VALIDOS}
    for estado, n in rows:
        if estado in counts:
            counts[estado] = int(n)
    total = sum(counts.values())
    return jsonify(
        StockResumen(total=total, **counts).model_dump()
    )


@bp.post("/ajuste")
@roles_required("admin")
def ajuste_stock():
    try:
        payload = StockAjusteRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )

    articulo = db.session.get(Articulo, payload.articulo_id)
    if articulo is None or articulo.deleted_at is not None:
        return error_response("articulo no encontrado", 404, "not_found")

    sucursal = db.session.get(Sucursal, payload.sucursal_id)
    if sucursal is None or sucursal.deleted_at is not None:
        return error_response("sucursal no encontrada", 404, "not_found")

    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        user_id = None

    row = stock_service.get_or_create(
        db.session, payload.articulo_id, payload.sucursal_id
    )
    cantidad_anterior = row.cantidad
    row.cantidad = payload.cantidad_nueva

    # Aplicar overrides de stock inteligente (si vienen)
    if payload.unset_stock_minimo:
        row.stock_minimo = None
    elif payload.stock_minimo is not None:
        row.stock_minimo = payload.stock_minimo

    if payload.unset_stock_maximo:
        row.stock_maximo = None
    elif payload.stock_maximo is not None:
        row.stock_maximo = payload.stock_maximo

    if payload.unset_punto_reorden:
        row.punto_reorden = None
    elif payload.punto_reorden is not None:
        row.punto_reorden = payload.punto_reorden

    if payload.unset_lead_time_dias:
        row.lead_time_dias = None
    elif payload.lead_time_dias is not None:
        row.lead_time_dias = payload.lead_time_dias

    ahora = datetime.now(UTC)
    db.session.add(
        MovimientoCaja(
            sucursal_id=payload.sucursal_id,
            caja_numero=1,
            fecha_caja=ahora.date(),
            fecha=ahora,
            tipo=TipoMovimientoEnum.ajuste,
            medio=None,
            monto=0,
            descripcion=(
                f"Ajuste stock art={payload.articulo_id} "
                f"{cantidad_anterior}→{payload.cantidad_nueva}: {payload.motivo}"
            ),
            user_id=user_id,
        )
    )
    db.session.commit()

    return jsonify(_serialize(row))


@bp.get("/<int:articulo_id>/sugerencia/<int:sucursal_id>")
@roles_required("admin", "supervisor", "contador")
def sugerencia_articulo(articulo_id: int, sucursal_id: int):
    """Devuelve velocidad calculada + stock óptimo sugerido para un articulo
    en una sucursal. Útil para el modal de ajuste (tab "Sugerencias")."""
    articulo = db.session.get(Articulo, articulo_id)
    if articulo is None or articulo.deleted_at is not None:
        return error_response("articulo no encontrado", 404, "not_found")
    sucursal = db.session.get(Sucursal, sucursal_id)
    if sucursal is None or sucursal.deleted_at is not None:
        return error_response("sucursal no encontrada", 404, "not_found")

    row = stock_service.get_or_create(db.session, articulo_id, sucursal_id)
    lead_time = row.efectivo_lead_time or LEAD_TIME_DEFAULT_DIAS
    velocidad = calcular_velocidad_venta(
        db.session, articulo_id, sucursal_id, dias=30
    )
    optimo = calcular_stock_optimo(
        velocidad["velocidad_promedio_diaria"], lead_time
    )

    # cantidad_a_pedir = max(optimo - cantidad, 0) — si ya hay óptimo seteado,
    # respetar ese; sino el calculado.
    return jsonify(
        {
            "articulo_id": articulo_id,
            "sucursal_id": sucursal_id,
            "cantidad_actual": str(row.cantidad),
            "lead_time_dias": lead_time,
            "velocidad": {
                "velocidad_promedio_diaria": str(
                    velocidad["velocidad_promedio_diaria"]
                ),
                "velocidad_dias_activos": str(
                    velocidad["velocidad_dias_activos"]
                ),
                "cantidad_total_vendida": str(
                    velocidad["cantidad_total_vendida"]
                ),
                "dias_con_venta": velocidad["dias_con_venta"],
                "dias": velocidad["dias"],
            },
            "stock_optimo_sugerido": str(optimo),
            "stock_optimo_calculado": (
                str(row.stock_optimo_calculado)
                if row.stock_optimo_calculado is not None
                else None
            ),
        }
    )
