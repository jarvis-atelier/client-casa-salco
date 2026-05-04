"""Endpoints de reportes agregados — para dashboard.

Estos endpoints son SOLO READ y devuelven agregaciones (group by) sobre facturas
y movimientos para alimentar charts. Diseñados para ser baratos: una sola query
cada uno, sin N+1, sin paginación.

Filtros comunes:
- fecha_desde / fecha_hasta (ISO date) — opcionales; default = últimos 30 días
- sucursal_id (int) — opcional; si no se pasa, agrupa todas las sucursales

RBAC: admin / supervisor / contador. El cajero ve sólo su sucursal.
"""
from __future__ import annotations

import hashlib
import json
import time
from datetime import date, datetime, timedelta
from decimal import Decimal

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt
from sqlalchemy import Integer, func, select

from app.extensions import db
from app.models.articulo import Articulo
from app.models.factura import EstadoComprobanteEnum, Factura
from app.models.factura_item import FacturaItem
from app.models.pago import FacturaPago
from app.models.sucursal import Sucursal
from app.services.excel import (
    build_cobranzas_export,
    build_compras_export,
    build_cta_cte_cliente_export,
    build_cta_cte_proveedor_export,
    build_libro_iva_digital,
    build_pagos_export,
    build_resumen_clientes,
    build_resumen_proveedores,
    build_stock_export,
    build_stock_valorizado,
    build_ventas_detallado,
    build_ventas_export,
)
from app.services.excel.builders import make_filename
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

bp = Blueprint("reports", __name__, url_prefix="/api/v1/reports")


# --- Helpers ------------------------------------------------------------------


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _resolve_range(
    desde_raw: str | None, hasta_raw: str | None
) -> tuple[datetime, datetime]:
    """Resuelve el rango fecha_desde/fecha_hasta. Default: últimos 30 días."""
    hasta = _parse_date(hasta_raw) or date.today()
    desde = _parse_date(desde_raw) or (hasta - timedelta(days=30))
    return (
        datetime.combine(desde, datetime.min.time()),
        datetime.combine(hasta, datetime.max.time()),
    )


def _resolve_sucursal_filter() -> tuple[int | None, str | None]:
    """Devuelve (sucursal_id, error). Cajero queda forzado a su sucursal."""
    claims = get_jwt()
    rol = claims.get("rol")
    user_sucursal = claims.get("sucursal_id")
    requested = request.args.get("sucursal_id", type=int)

    if rol == "cajero" and user_sucursal:
        return user_sucursal, None
    return requested, None


def _is_postgres() -> bool:
    return db.engine.dialect.name == "postgresql"


def _date_trunc_day(col):
    """Trunca un timestamp a día. Compatible postgres / sqlite."""
    if _is_postgres():
        return func.date_trunc("day", col)
    # SQLite — devuelve string YYYY-MM-DD
    return func.strftime("%Y-%m-%d", col)


def _extract_dow(col):
    """Día de la semana 0=Lunes ... 6=Domingo. Compatible postgres / sqlite.

    Postgres `extract(dow from ...)` da 0=Domingo ... 6=Sábado, así que ajustamos.
    SQLite `strftime('%w', ...)` da 0=Domingo ... 6=Sábado también.
    Convertimos a 0=Lunes ... 6=Domingo via (dow + 6) % 7.
    """
    if _is_postgres():
        # postgres extract devuelve double, casteamos a int
        raw = func.cast(func.extract("dow", col), Integer)
    else:
        raw = func.cast(func.strftime("%w", col), Integer)
    return (raw + 6) % 7


def _extract_hour(col):
    if _is_postgres():
        return func.cast(func.extract("hour", col), Integer)
    return func.cast(func.strftime("%H", col), Integer)


def _decimal_str(v: Decimal | float | int | None) -> str:
    if v is None:
        return "0"
    return f"{Decimal(v):.2f}"


# --- Endpoints ----------------------------------------------------------------


@bp.get("/ventas-resumen")
@roles_required("admin", "supervisor", "contador", "cajero")
def ventas_resumen():
    """KPIs del período + variación vs período anterior + breakdown por sucursal."""
    desde, hasta = _resolve_range(
        request.args.get("fecha_desde"), request.args.get("fecha_hasta")
    )
    sucursal_id, err = _resolve_sucursal_filter()
    if err:
        return error_response(err, 422, "validation_error")

    base_where = [
        Factura.fecha >= desde,
        Factura.fecha <= hasta,
        Factura.estado == EstadoComprobanteEnum.emitida,
    ]
    if sucursal_id:
        base_where.append(Factura.sucursal_id == sucursal_id)

    # Totales del período
    stmt = select(
        func.count(Factura.id).label("cantidad"),
        func.coalesce(func.sum(Factura.total), 0).label("total"),
        func.coalesce(func.sum(Factura.total_iva), 0).label("iva"),
    ).where(*base_where)
    row = db.session.execute(stmt).one()
    cantidad = int(row.cantidad or 0)
    total = Decimal(row.total or 0)
    iva = Decimal(row.iva or 0)
    ticket_promedio = (total / cantidad) if cantidad else Decimal("0")

    # Período anterior (mismo largo, inmediatamente antes) para variación
    delta = hasta - desde
    desde_prev = desde - delta - timedelta(microseconds=1)
    hasta_prev = desde - timedelta(microseconds=1)
    prev_where = [
        Factura.fecha >= desde_prev,
        Factura.fecha <= hasta_prev,
        Factura.estado == EstadoComprobanteEnum.emitida,
    ]
    if sucursal_id:
        prev_where.append(Factura.sucursal_id == sucursal_id)
    prev_stmt = select(
        func.count(Factura.id).label("cantidad"),
        func.coalesce(func.sum(Factura.total), 0).label("total"),
        func.coalesce(func.sum(Factura.total_iva), 0).label("iva"),
    ).where(*prev_where)
    prev_row = db.session.execute(prev_stmt).one()
    prev_cantidad = int(prev_row.cantidad or 0)
    prev_total = Decimal(prev_row.total or 0)
    prev_iva = Decimal(prev_row.iva or 0)
    prev_ticket = (prev_total / prev_cantidad) if prev_cantidad else Decimal("0")

    def _var_pct(curr: Decimal, prev: Decimal) -> float | None:
        if prev == 0:
            return None
        return float((curr - prev) / prev * 100)

    # Breakdown por sucursal
    suc_stmt = (
        select(
            Sucursal.id,
            Sucursal.codigo,
            Sucursal.nombre,
            func.count(Factura.id).label("cantidad"),
            func.coalesce(func.sum(Factura.total), 0).label("total"),
        )
        .select_from(Sucursal)
        .join(Factura, Factura.sucursal_id == Sucursal.id)
        .where(*base_where)
        .group_by(Sucursal.id, Sucursal.codigo, Sucursal.nombre)
        .order_by(func.sum(Factura.total).desc())
    )
    por_sucursal = [
        {
            "sucursal_id": r.id,
            "codigo": r.codigo,
            "nombre": r.nombre,
            "cantidad": int(r.cantidad or 0),
            "total": _decimal_str(r.total),
        }
        for r in db.session.execute(suc_stmt).all()
    ]

    return jsonify(
        {
            "fecha_desde": desde.date().isoformat(),
            "fecha_hasta": hasta.date().isoformat(),
            "sucursal_id": sucursal_id,
            "total_facturas": cantidad,
            "total_facturado": _decimal_str(total),
            "total_iva": _decimal_str(iva),
            "ticket_promedio": _decimal_str(ticket_promedio),
            "var_total_pct": _var_pct(total, prev_total),
            "var_cantidad_pct": _var_pct(Decimal(cantidad), Decimal(prev_cantidad)),
            "var_ticket_pct": _var_pct(ticket_promedio, prev_ticket),
            "var_iva_pct": _var_pct(iva, prev_iva),
            "prev_total_facturado": _decimal_str(prev_total),
            "prev_total_facturas": prev_cantidad,
            "por_sucursal": por_sucursal,
        }
    )


@bp.get("/ventas-por-dia")
@roles_required("admin", "supervisor", "contador", "cajero")
def ventas_por_dia():
    """Serie temporal de ventas. Group by día, opcional break por sucursal."""
    desde, hasta = _resolve_range(
        request.args.get("fecha_desde"), request.args.get("fecha_hasta")
    )
    sucursal_id, err = _resolve_sucursal_filter()
    if err:
        return error_response(err, 422, "validation_error")

    where = [
        Factura.fecha >= desde,
        Factura.fecha <= hasta,
        Factura.estado == EstadoComprobanteEnum.emitida,
    ]
    if sucursal_id:
        where.append(Factura.sucursal_id == sucursal_id)

    fecha_col = _date_trunc_day(Factura.fecha).label("dia")

    stmt = (
        select(
            fecha_col,
            Sucursal.codigo.label("sucursal_codigo"),
            func.count(Factura.id).label("cantidad"),
            func.coalesce(func.sum(Factura.total), 0).label("total"),
        )
        .select_from(Factura)
        .join(Sucursal, Sucursal.id == Factura.sucursal_id)
        .where(*where)
        .group_by(fecha_col, Sucursal.codigo)
        .order_by(fecha_col)
    )

    rows = db.session.execute(stmt).all()

    # Agrupamos por día. Para cada día acumulamos por sucursal y total.
    by_day: dict[str, dict] = {}
    for r in rows:
        # En postgres, dia es datetime; en sqlite, string
        if isinstance(r.dia, str):
            fecha_iso = r.dia[:10]
        elif isinstance(r.dia, datetime):
            fecha_iso = r.dia.date().isoformat()
        elif isinstance(r.dia, date):
            fecha_iso = r.dia.isoformat()
        else:
            fecha_iso = str(r.dia)[:10]
        bucket = by_day.setdefault(
            fecha_iso, {"fecha": fecha_iso, "total": Decimal("0"), "cantidad": 0, "por_sucursal": {}}
        )
        bucket["total"] += Decimal(r.total or 0)
        bucket["cantidad"] += int(r.cantidad or 0)
        bucket["por_sucursal"][r.sucursal_codigo] = _decimal_str(r.total)

    out = [
        {
            "fecha": d["fecha"],
            "total": _decimal_str(d["total"]),
            "cantidad": d["cantidad"],
            "por_sucursal": d["por_sucursal"],
        }
        for d in sorted(by_day.values(), key=lambda x: x["fecha"])
    ]
    return jsonify(out)


@bp.get("/top-productos")
@roles_required("admin", "supervisor", "contador", "cajero")
def top_productos():
    """Top N artículos por cantidad vendida. Limit default = 10, max 50."""
    desde, hasta = _resolve_range(
        request.args.get("fecha_desde"), request.args.get("fecha_hasta")
    )
    sucursal_id, err = _resolve_sucursal_filter()
    if err:
        return error_response(err, 422, "validation_error")

    limit = request.args.get("limit", default=10, type=int)
    limit = max(1, min(limit, 50))

    where = [
        Factura.fecha >= desde,
        Factura.fecha <= hasta,
        Factura.estado == EstadoComprobanteEnum.emitida,
    ]
    if sucursal_id:
        where.append(Factura.sucursal_id == sucursal_id)

    stmt = (
        select(
            Articulo.id.label("articulo_id"),
            Articulo.codigo,
            Articulo.descripcion,
            func.coalesce(func.sum(FacturaItem.cantidad), 0).label("cantidad_vendida"),
            func.coalesce(func.sum(FacturaItem.total), 0).label("total_facturado"),
        )
        .select_from(FacturaItem)
        .join(Factura, Factura.id == FacturaItem.factura_id)
        .join(Articulo, Articulo.id == FacturaItem.articulo_id)
        .where(*where)
        .group_by(Articulo.id, Articulo.codigo, Articulo.descripcion)
        .order_by(func.sum(FacturaItem.cantidad).desc())
        .limit(limit)
    )

    rows = db.session.execute(stmt).all()
    return jsonify(
        [
            {
                "articulo_id": r.articulo_id,
                "codigo": r.codigo,
                "descripcion": r.descripcion,
                "cantidad_vendida": _decimal_str(r.cantidad_vendida),
                "total_facturado": _decimal_str(r.total_facturado),
            }
            for r in rows
        ]
    )


@bp.get("/ventas-por-hora")
@roles_required("admin", "supervisor", "contador", "cajero")
def ventas_por_hora():
    """Heatmap día-de-semana × hora. Devuelve celdas con cantidad y total.

    dia_semana: 0=Lunes ... 6=Domingo.
    hora: 0..23.
    """
    desde, hasta = _resolve_range(
        request.args.get("fecha_desde"), request.args.get("fecha_hasta")
    )
    sucursal_id, err = _resolve_sucursal_filter()
    if err:
        return error_response(err, 422, "validation_error")

    where = [
        Factura.fecha >= desde,
        Factura.fecha <= hasta,
        Factura.estado == EstadoComprobanteEnum.emitida,
    ]
    if sucursal_id:
        where.append(Factura.sucursal_id == sucursal_id)

    dow = _extract_dow(Factura.fecha).label("dow")
    hora = _extract_hour(Factura.fecha).label("hora")

    stmt = (
        select(
            dow,
            hora,
            func.count(Factura.id).label("cantidad"),
            func.coalesce(func.sum(Factura.total), 0).label("total"),
        )
        .where(*where)
        .group_by(dow, hora)
        .order_by(dow, hora)
    )
    rows = db.session.execute(stmt).all()
    return jsonify(
        [
            {
                "dia_semana": int(r.dow),
                "hora": int(r.hora),
                "cantidad": int(r.cantidad or 0),
                "total": _decimal_str(r.total),
            }
            for r in rows
        ]
    )


@bp.get("/medios-pago")
@roles_required("admin", "supervisor", "contador", "cajero")
def medios_pago():
    """Distribución por medio de pago (cantidad de pagos + total + porcentaje)."""
    desde, hasta = _resolve_range(
        request.args.get("fecha_desde"), request.args.get("fecha_hasta")
    )
    sucursal_id, err = _resolve_sucursal_filter()
    if err:
        return error_response(err, 422, "validation_error")

    where = [
        Factura.fecha >= desde,
        Factura.fecha <= hasta,
        Factura.estado == EstadoComprobanteEnum.emitida,
    ]
    if sucursal_id:
        where.append(Factura.sucursal_id == sucursal_id)

    stmt = (
        select(
            FacturaPago.medio.label("medio"),
            func.count(FacturaPago.id).label("cantidad"),
            func.coalesce(func.sum(FacturaPago.monto), 0).label("total"),
        )
        .select_from(FacturaPago)
        .join(Factura, Factura.id == FacturaPago.factura_id)
        .where(*where)
        .group_by(FacturaPago.medio)
        .order_by(func.sum(FacturaPago.monto).desc())
    )
    rows = db.session.execute(stmt).all()
    total_global = sum((Decimal(r.total or 0) for r in rows), Decimal("0"))
    out = []
    for r in rows:
        total = Decimal(r.total or 0)
        porc = float(total / total_global * 100) if total_global > 0 else 0.0
        # `medio` puede llegar como Enum o string según dialect
        medio_str = r.medio.value if hasattr(r.medio, "value") else str(r.medio)
        out.append(
            {
                "medio": medio_str,
                "cantidad": int(r.cantidad or 0),
                "total": _decimal_str(total),
                "porc": round(porc, 2),
            }
        )
    return jsonify(out)


# --- Correlaciones de productos (Apriori / Market Basket) ---------------------

# Cache in-memory simple por hash de params, TTL 1 hora.
_CORRELACIONES_CACHE: dict[str, tuple[float, dict]] = {}
_CORRELACIONES_TTL_SECONDS = 3600


def _cache_key(params: dict) -> str:
    canonical = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@bp.get("/correlaciones")
@roles_required("admin", "supervisor")
def correlaciones():
    """Market basket analysis: productos comprados juntos.

    Query params:
      - fecha_desde / fecha_hasta (ISO date, opcionales; default: últimos 90 días)
      - sucursal_id (opcional)
      - soporte_min (float 0..1, default 0.01)
      - confianza_min (float 0..1, default 0.30)
      - lift_min (float, default 1.5)
      - top_n (int, default 50, max 200)
      - force_recompute (bool, default false)

    Devuelve un objeto con metadata + lista de reglas ordenadas por lift desc.
    Cache in-memory por (params + sucursal del cajero) con TTL de 1h.
    """
    desde = _parse_date(request.args.get("fecha_desde"))
    hasta = _parse_date(request.args.get("fecha_hasta"))
    sucursal_id, err = _resolve_sucursal_filter()
    if err:
        return error_response(err, 422, "validation_error")

    def _f(name: str, default: float, lo: float, hi: float) -> float:
        raw = request.args.get(name)
        if raw is None:
            return default
        try:
            v = float(raw)
        except ValueError:
            return default
        return max(lo, min(hi, v))

    # Defaults adaptados a almacén típico (catálogo grande, soportes bajos):
    # 0.2% soporte ≈ ~1/500 transacciones; conf 10% y lift 1.2 ya filtran ruido.
    soporte_min = _f("soporte_min", 0.002, 0.0005, 1.0)
    confianza_min = _f("confianza_min", 0.10, 0.0, 1.0)
    lift_min = _f("lift_min", 1.2, 0.0, 1000.0)
    top_n = request.args.get("top_n", default=50, type=int) or 50
    top_n = max(1, min(top_n, 200))
    force = request.args.get("force_recompute", "").lower() in ("1", "true", "yes")

    cache_params = {
        "fecha_desde": desde.isoformat() if desde else None,
        "fecha_hasta": hasta.isoformat() if hasta else None,
        "sucursal_id": sucursal_id,
        "soporte_min": soporte_min,
        "confianza_min": confianza_min,
        "lift_min": lift_min,
        "top_n": top_n,
    }
    key = _cache_key(cache_params)
    now = time.time()

    if not force:
        hit = _CORRELACIONES_CACHE.get(key)
        if hit is not None:
            ts, payload = hit
            if now - ts < _CORRELACIONES_TTL_SECONDS:
                return jsonify({**payload, "cached": True})

    # Importamos acá para que el módulo cargue rápido aunque mlxtend no esté.
    from app.services.analytics.correlaciones import calcular_correlaciones

    try:
        result = calcular_correlaciones(
            db.session,
            fecha_desde=desde,
            fecha_hasta=hasta,
            sucursal_id=sucursal_id,
            soporte_min=soporte_min,
            confianza_min=confianza_min,
            lift_min=lift_min,
            top_n=top_n,
        )
    except ImportError as exc:
        return error_response(
            f"analytics no disponible: {exc}", 503, "service_unavailable"
        )
    except Exception as exc:  # pragma: no cover - defensive
        return error_response(
            f"error calculando correlaciones: {exc}", 500, "internal_error"
        )

    _CORRELACIONES_CACHE[key] = (now, result)
    return jsonify({**result, "cached": False})


# --- Exports XLSX -------------------------------------------------------------
#
# Endpoints de descarga directa para el contador. Devuelven .xlsx con
# Content-Disposition: attachment. El frontend los consume con
# `responseType: 'blob'` y dispara el download via blob URL.
#
# RBAC: solo admin / supervisor / contador. El cajero NO puede exportar libros
# fiscales completos.


def _xlsx_response(data: bytes, filename: str) -> Response:
    response = Response(data, mimetype=XLSX_MIME)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Content-Length"] = str(len(data))
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/libro-iva-digital.xlsx")
@roles_required("admin", "supervisor", "contador")
def libro_iva_digital_xlsx():
    """Genera el Libro IVA Digital (RG 4597) — sheets Ventas + Compras."""
    desde_raw = request.args.get("fecha_desde")
    hasta_raw = request.args.get("fecha_hasta")
    hasta = _parse_date(hasta_raw) or date.today().replace(day=1) - timedelta(days=1)
    # Por defecto: mes anterior completo (qué es lo que el contador presenta)
    if not desde_raw:
        desde = hasta.replace(day=1)
    else:
        desde = _parse_date(desde_raw) or hasta.replace(day=1)
    if desde > hasta:
        return error_response(
            "fecha_desde debe ser <= fecha_hasta", 422, "validation_error"
        )

    data = build_libro_iva_digital(db.session, desde, hasta)
    filename = make_filename("libro-iva-digital", desde, hasta)
    return _xlsx_response(data, filename)


@bp.get("/ventas-export.xlsx")
@roles_required("admin", "supervisor", "contador")
def ventas_export_xlsx():
    """Export detallado de ventas + resumen diario."""
    desde_raw = request.args.get("fecha_desde")
    hasta_raw = request.args.get("fecha_hasta")
    hasta = _parse_date(hasta_raw) or date.today()
    desde = _parse_date(desde_raw) or (hasta - timedelta(days=30))
    if desde > hasta:
        return error_response(
            "fecha_desde debe ser <= fecha_hasta", 422, "validation_error"
        )

    sucursal_id = request.args.get("sucursal_id", type=int)
    data = build_ventas_export(db.session, desde, hasta, sucursal_id=sucursal_id)
    filename = make_filename("ventas", desde, hasta)
    return _xlsx_response(data, filename)


@bp.get("/stock-export.xlsx")
@roles_required("admin", "supervisor", "contador")
def stock_export_xlsx():
    """Export de stock por (artículo × sucursal). Snapshot al momento."""
    sucursal_id = request.args.get("sucursal_id", type=int)
    data = build_stock_export(db.session, sucursal_id=sucursal_id)
    filename = make_filename("stock")
    return _xlsx_response(data, filename)


@bp.get("/lista-reposicion.xlsx")
@roles_required("admin", "supervisor", "contador")
def lista_reposicion_xlsx():
    """Lista de reposición agrupada por proveedor para mandar al proveedor.

    Una sheet "Resumen" + una sheet por proveedor con sugerencias de pedido.
    """
    from app.services.excel import build_lista_reposicion

    sucursal_id = request.args.get("sucursal_id", type=int)
    data = build_lista_reposicion(db.session, sucursal_id=sucursal_id)
    filename = make_filename("lista-reposicion")
    return _xlsx_response(data, filename)


# --- Exports nuevos: compras / cobranzas / pagos / cta cte / resúmenes -------


def _resolve_date_range_required() -> tuple[date, date] | tuple[None, Response]:
    """Parsea fecha_desde/fecha_hasta. Default = últimos 30 días."""
    desde_raw = request.args.get("fecha_desde")
    hasta_raw = request.args.get("fecha_hasta")
    hasta = _parse_date(hasta_raw) or date.today()
    desde = _parse_date(desde_raw) or (hasta - timedelta(days=30))
    if desde > hasta:
        return None, error_response(
            "fecha_desde debe ser <= fecha_hasta", 422, "validation_error"
        )
    return desde, hasta


@bp.get("/compras-export.xlsx")
@roles_required("admin", "supervisor", "contador")
def compras_export_xlsx():
    """Export de compras (Factura tipo C) en rango con filtros."""
    res = _resolve_date_range_required()
    if res[0] is None:
        return res[1]
    desde, hasta = res
    proveedor_id = request.args.get("proveedor_id", type=int)
    sucursal_id = request.args.get("sucursal_id", type=int)
    data = build_compras_export(
        db.session, desde, hasta, proveedor_id=proveedor_id, sucursal_id=sucursal_id
    )
    filename = make_filename("compras", desde, hasta)
    return _xlsx_response(data, filename)


@bp.get("/cobranzas-export.xlsx")
@roles_required("admin", "supervisor", "contador")
def cobranzas_export_xlsx():
    """Export de cobranzas (movimientos tipo cobranza) en rango."""
    res = _resolve_date_range_required()
    if res[0] is None:
        return res[1]
    desde, hasta = res
    cliente_id = request.args.get("cliente_id", type=int)
    sucursal_id = request.args.get("sucursal_id", type=int)
    data = build_cobranzas_export(
        db.session, desde, hasta, cliente_id=cliente_id, sucursal_id=sucursal_id
    )
    filename = make_filename("cobranzas", desde, hasta)
    return _xlsx_response(data, filename)


@bp.get("/pagos-export.xlsx")
@roles_required("admin", "supervisor", "contador")
def pagos_export_xlsx():
    """Export de pagos a proveedores (movimientos tipo pago_proveedor)."""
    res = _resolve_date_range_required()
    if res[0] is None:
        return res[1]
    desde, hasta = res
    proveedor_id = request.args.get("proveedor_id", type=int)
    sucursal_id = request.args.get("sucursal_id", type=int)
    data = build_pagos_export(
        db.session, desde, hasta, proveedor_id=proveedor_id, sucursal_id=sucursal_id
    )
    filename = make_filename("pagos", desde, hasta)
    return _xlsx_response(data, filename)


@bp.get("/cta-cte-cliente.xlsx")
@roles_required("admin", "supervisor", "contador")
def cta_cte_cliente_xlsx():
    """Histórico de cuenta corriente de un cliente."""
    cliente_id = request.args.get("cliente_id", type=int)
    if not cliente_id:
        return error_response("cliente_id es requerido", 422, "validation_error")
    desde = _parse_date(request.args.get("fecha_desde"))
    hasta = _parse_date(request.args.get("fecha_hasta"))
    try:
        data = build_cta_cte_cliente_export(
            db.session, cliente_id, fecha_desde=desde, fecha_hasta=hasta
        )
    except ValueError as exc:
        return error_response(str(exc), 404, "not_found")
    filename = make_filename(f"cta-cte-cliente-{cliente_id}", desde, hasta)
    return _xlsx_response(data, filename)


@bp.get("/cta-cte-proveedor.xlsx")
@roles_required("admin", "supervisor", "contador")
def cta_cte_proveedor_xlsx():
    """Histórico de cuenta corriente de un proveedor."""
    proveedor_id = request.args.get("proveedor_id", type=int)
    if not proveedor_id:
        return error_response("proveedor_id es requerido", 422, "validation_error")
    desde = _parse_date(request.args.get("fecha_desde"))
    hasta = _parse_date(request.args.get("fecha_hasta"))
    try:
        data = build_cta_cte_proveedor_export(
            db.session, proveedor_id, fecha_desde=desde, fecha_hasta=hasta
        )
    except ValueError as exc:
        return error_response(str(exc), 404, "not_found")
    filename = make_filename(f"cta-cte-proveedor-{proveedor_id}", desde, hasta)
    return _xlsx_response(data, filename)


@bp.get("/resumen-clientes.xlsx")
@roles_required("admin", "supervisor", "contador")
def resumen_clientes_xlsx():
    """Listado completo de clientes con saldo y última operación."""
    data = build_resumen_clientes(db.session)
    filename = make_filename("resumen-clientes")
    return _xlsx_response(data, filename)


@bp.get("/resumen-proveedores.xlsx")
@roles_required("admin", "supervisor", "contador")
def resumen_proveedores_xlsx():
    """Listado de proveedores con compras totales."""
    data = build_resumen_proveedores(db.session)
    filename = make_filename("resumen-proveedores")
    return _xlsx_response(data, filename)


@bp.get("/stock-valorizado.xlsx")
@roles_required("admin", "supervisor", "contador")
def stock_valorizado_xlsx():
    """Stock con costo, valor total y % del valor."""
    sucursal_id = request.args.get("sucursal_id", type=int)
    data = build_stock_valorizado(db.session, sucursal_id=sucursal_id)
    filename = make_filename("stock-valorizado")
    return _xlsx_response(data, filename)


@bp.get("/ventas-detallado.xlsx")
@roles_required("admin", "supervisor", "contador")
def ventas_detallado_xlsx():
    """Ventas detallado con sheets agrupados por sucursal/familia/cajero/top productos."""
    res = _resolve_date_range_required()
    if res[0] is None:
        return res[1]
    desde, hasta = res
    sucursal_id = request.args.get("sucursal_id", type=int)
    data = build_ventas_detallado(
        db.session, desde, hasta, sucursal_id=sucursal_id
    )
    filename = make_filename("ventas-detallado", desde, hasta)
    return _xlsx_response(data, filename)
