"""Pantalla de Consultas (F3 del sistema viejo) — endpoints genéricos paginados.

Una entidad por path. Cada entidad acepta:
  - filtros comunes: q (text), fecha_desde, fecha_hasta, sucursal_id
  - filtros específicos según entidad
  - page, per_page para paginación

Para cada entidad existe la versión `.xlsx` que devuelve el mismo conjunto de
filas pero como Excel.

Diseño:
- `_query_<entidad>` arma el query SA y devuelve `(stmt_for_paginate, project_fn,
  headers, formats)`. La proyección se aplica row-by-row para JSON o Excel.
- Endpoint JSON: `GET /consultas/<entidad>` → paginado.
- Endpoint Excel: `GET /consultas/<entidad>.xlsx` → bytes con Workbook.

RBAC:
  - Listado JSON: admin / supervisor / contador (cajero solo a lo suyo).
  - .xlsx: admin / supervisor / contador (cajero NO).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import Decimal
from math import ceil
from typing import Any, Callable

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.extensions import db
from app.models.alerta import Alerta, EstadoAlertaEnum, SeveridadEnum, TipoAlertaEnum
from app.models.articulo import Articulo
from app.models.cae import Cae
from app.models.cliente import Cliente
from app.models.factura import EstadoComprobanteEnum, Factura, TipoComprobanteEnum
from app.models.pago import MedioPagoEnum
from app.models.proveedor import Proveedor
from app.models.resumen import MovimientoCaja, TipoMovimientoEnum
from app.models.stock import StockSucursal
from app.models.sucursal import Sucursal
from app.services.excel.builders import build_generic_export, make_filename
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

bp = Blueprint("consultas", __name__, url_prefix="/api/v1/consultas")


# --- Helpers ----------------------------------------------------------------


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def _resolve_range(default_days: int = 30) -> tuple[datetime, datetime]:
    desde_raw = request.args.get("fecha_desde")
    hasta_raw = request.args.get("fecha_hasta")
    hasta_d = _parse_date(hasta_raw) or date.today()
    desde_d = _parse_date(desde_raw) or (hasta_d - timedelta(days=default_days))
    return (
        datetime.combine(desde_d, datetime.min.time()),
        datetime.combine(hasta_d, datetime.max.time()),
    )


def _resolve_sucursal_filter() -> int | None:
    claims = get_jwt()
    rol = claims.get("rol")
    user_sucursal = claims.get("sucursal_id")
    requested = request.args.get("sucursal_id", type=int)
    if rol == "cajero" and user_sucursal:
        return user_sucursal
    return requested


def _get_page_params() -> tuple[int, int]:
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        per_page = int(request.args.get("per_page", 50))
    except (TypeError, ValueError):
        per_page = 50
    per_page = max(1, min(per_page, 200))
    return page, per_page


def _decimal(v: Any) -> Decimal:
    if v is None:
        return Decimal("0")
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _xlsx_response(data: bytes, filename: str) -> Response:
    response = Response(data, mimetype=XLSX_MIME)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Content-Length"] = str(len(data))
    response.headers["Cache-Control"] = "no-store"
    return response


def _legacy_proveedor_id(factura: Factura) -> int | None:
    if not factura.legacy_meta:
        return None
    raw = factura.legacy_meta.get("proveedor_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


# --- Definición de entidades -------------------------------------------------
#
# Cada entidad expone:
#   list_rows(session) -> (rows, total_count, headers, project_excel, formats)
# Donde:
#   rows: list[dict] proyectado para JSON (page slice)
#   total_count: int total ignorando paginación
#   headers: list[str] cabeceras del Excel
#   project_excel: callable(row_dict) -> list[Any] para una fila del Excel.
#                  Se llama sobre TODAS las filas (sin paginación) cuando se exporta.
#   formats: dict {col_idx_1based: 'currency'|'date'|'int'|'percent'}


def _query_clientes(session: Session, *, for_excel: bool):
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

    def proyectar(c: Cliente) -> dict[str, Any]:
        return {
            "id": c.id,
            "codigo": c.codigo,
            "razon_social": c.razon_social,
            "cuit": c.cuit or "",
            "condicion_iva": c.condicion_iva.value,
            "cuenta_corriente": c.cuenta_corriente,
            "limite_cuenta_corriente": str(_decimal(c.limite_cuenta_corriente)),
            "saldo": str(_decimal(c.saldo)),
            "activo": c.activo,
            "email": c.email or "",
            "telefono": c.telefono or "",
        }

    headers = [
        "Código",
        "Razón social",
        "CUIT",
        "Cond. IVA",
        "Cta. Cte.",
        "Límite",
        "Saldo",
        "Activo",
        "Email",
        "Teléfono",
    ]

    def excel_row(d: dict[str, Any]) -> list[Any]:
        return [
            d["codigo"],
            d["razon_social"],
            d["cuit"],
            d["condicion_iva"],
            "Sí" if d["cuenta_corriente"] else "No",
            float(_decimal(d["limite_cuenta_corriente"])),
            float(_decimal(d["saldo"])),
            "Sí" if d["activo"] else "No",
            d["email"],
            d["telefono"],
        ]

    formats = {6: "currency", 7: "currency"}
    return stmt, proyectar, headers, excel_row, formats


def _query_proveedores(session: Session, *, for_excel: bool):
    q = (request.args.get("q") or "").strip()
    stmt = select(Proveedor).where(Proveedor.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Proveedor.codigo.ilike(like),
                Proveedor.razon_social.ilike(like),
                Proveedor.cuit.ilike(like),
            )
        )
    stmt = stmt.order_by(Proveedor.razon_social)

    def proyectar(p: Proveedor) -> dict[str, Any]:
        return {
            "id": p.id,
            "codigo": p.codigo,
            "razon_social": p.razon_social,
            "cuit": p.cuit or "",
            "email": p.email or "",
            "telefono": p.telefono or "",
            "direccion": p.direccion or "",
            "activo": p.activo,
        }

    headers = ["Código", "Razón social", "CUIT", "Email", "Teléfono", "Dirección", "Activo"]

    def excel_row(d: dict[str, Any]) -> list[Any]:
        return [
            d["codigo"],
            d["razon_social"],
            d["cuit"],
            d["email"],
            d["telefono"],
            d["direccion"],
            "Sí" if d["activo"] else "No",
        ]

    return stmt, proyectar, headers, excel_row, {}


def _query_articulos(session: Session, *, for_excel: bool):
    q = (request.args.get("q") or "").strip()
    activo = request.args.get("activo")
    stmt = select(Articulo).where(Articulo.deleted_at.is_(None))
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Articulo.codigo.ilike(like),
                Articulo.descripcion.ilike(like),
                Articulo.codigo_barras.ilike(like),
            )
        )
    if activo is not None:
        stmt = stmt.where(Articulo.activo.is_(activo.lower() in ("1", "true", "yes")))
    stmt = stmt.order_by(Articulo.codigo)

    def proyectar(a: Articulo) -> dict[str, Any]:
        return {
            "id": a.id,
            "codigo": a.codigo,
            "descripcion": a.descripcion,
            "unidad_medida": a.unidad_medida.value,
            "costo": str(_decimal(a.costo)),
            "pvp_base": str(_decimal(a.pvp_base)),
            "iva_porc": str(_decimal(a.iva_porc)),
            "controla_stock": a.controla_stock,
            "activo": a.activo,
        }

    headers = [
        "Código",
        "Descripción",
        "Unidad",
        "Costo",
        "PVP base",
        "IVA %",
        "Controla stock",
        "Activo",
    ]

    def excel_row(d: dict[str, Any]) -> list[Any]:
        return [
            d["codigo"],
            d["descripcion"],
            d["unidad_medida"],
            float(_decimal(d["costo"])),
            float(_decimal(d["pvp_base"])),
            float(_decimal(d["iva_porc"])),
            "Sí" if d["controla_stock"] else "No",
            "Sí" if d["activo"] else "No",
        ]

    formats = {4: "currency", 5: "currency"}
    return stmt, proyectar, headers, excel_row, formats


def _query_facturas_tipo(
    session: Session, *, tipos_in: list[TipoComprobanteEnum] | None, exclude_compra: bool
):
    desde, hasta = _resolve_range()
    sucursal_id = _resolve_sucursal_filter()
    q = (request.args.get("q") or "").strip()
    stmt = (
        select(Factura, Sucursal, Cliente)
        .join(Sucursal, Sucursal.id == Factura.sucursal_id)
        .outerjoin(Cliente, Cliente.id == Factura.cliente_id)
        .where(
            Factura.fecha >= desde,
            Factura.fecha <= hasta,
            Factura.estado == EstadoComprobanteEnum.emitida,
        )
    )
    if tipos_in:
        stmt = stmt.where(Factura.tipo.in_(tipos_in))
    elif exclude_compra:
        stmt = stmt.where(Factura.tipo != TipoComprobanteEnum.factura_c)
    if sucursal_id:
        stmt = stmt.where(Factura.sucursal_id == sucursal_id)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(
            or_(
                Cliente.razon_social.ilike(like),
                Cliente.cuit.ilike(like),
            )
        )
    stmt = stmt.order_by(Factura.fecha.desc(), Factura.id.desc())
    return stmt


def _query_ventas(session: Session, *, for_excel: bool):
    stmt = _query_facturas_tipo(session, tipos_in=None, exclude_compra=True)

    def proyectar(triple) -> dict[str, Any]:
        f, s, c = triple
        fecha_dia = f.fecha.date() if isinstance(f.fecha, datetime) else f.fecha
        return {
            "id": f.id,
            "fecha": fecha_dia.isoformat(),
            "tipo": f.tipo.value,
            "punto_venta": f.punto_venta,
            "numero": f.numero,
            "sucursal": f"{s.codigo} - {s.nombre}",
            "cliente": c.razon_social if c else "Consumidor Final",
            "cuit": c.cuit if c else "",
            "subtotal": str(_decimal(f.subtotal)),
            "iva": str(_decimal(f.total_iva)),
            "total": str(_decimal(f.total)),
            "estado": f.estado.value,
        }

    headers = [
        "Fecha",
        "Tipo",
        "Comprobante",
        "Sucursal",
        "Cliente",
        "CUIT",
        "Subtotal",
        "IVA",
        "Total",
        "Estado",
    ]

    def excel_row(d: dict[str, Any]) -> list[Any]:
        return [
            date.fromisoformat(d["fecha"]),
            d["tipo"],
            f"{int(d['punto_venta']):04d}-{int(d['numero']):08d}",
            d["sucursal"],
            d["cliente"],
            d["cuit"],
            float(_decimal(d["subtotal"])),
            float(_decimal(d["iva"])),
            float(_decimal(d["total"])),
            d["estado"],
        ]

    formats = {1: "date", 7: "currency", 8: "currency", 9: "currency"}
    return stmt, proyectar, headers, excel_row, formats


def _query_compras(session: Session, *, for_excel: bool):
    stmt = _query_facturas_tipo(
        session, tipos_in=[TipoComprobanteEnum.factura_c], exclude_compra=False
    )
    proveedor_id = request.args.get("proveedor_id", type=int)

    proveedores = {p.id: p for p in session.execute(select(Proveedor)).scalars().all()}

    def proyectar(triple) -> dict[str, Any]:
        f, s, _c = triple
        prov_id = _legacy_proveedor_id(f)
        prov = proveedores.get(prov_id) if prov_id else None
        fecha_dia = f.fecha.date() if isinstance(f.fecha, datetime) else f.fecha
        nro = (f.legacy_meta or {}).get("numero_proveedor") or (
            f"{f.punto_venta:04d}-{f.numero:08d}"
        )
        return {
            "id": f.id,
            "fecha": fecha_dia.isoformat(),
            "comprobante": str(nro),
            "proveedor_id": prov.id if prov else None,
            "proveedor": prov.razon_social if prov else (
                (f.legacy_meta or {}).get("proveedor_nombre_raw") or "Sin proveedor"
            ),
            "cuit": prov.cuit if prov else "",
            "sucursal": f"{s.codigo} - {s.nombre}",
            "subtotal": str(_decimal(f.subtotal)),
            "iva": str(_decimal(f.total_iva)),
            "total": str(_decimal(f.total)),
            "estado": f.estado.value,
        }

    headers = [
        "Fecha",
        "Comprobante",
        "Proveedor",
        "CUIT",
        "Sucursal",
        "Subtotal",
        "IVA",
        "Total",
        "Estado",
    ]

    def excel_row(d: dict[str, Any]) -> list[Any]:
        return [
            date.fromisoformat(d["fecha"]),
            d["comprobante"],
            d["proveedor"],
            d["cuit"],
            d["sucursal"],
            float(_decimal(d["subtotal"])),
            float(_decimal(d["iva"])),
            float(_decimal(d["total"])),
            d["estado"],
        ]

    formats = {1: "date", 6: "currency", 7: "currency", 8: "currency"}

    # filtro proveedor en post-proyección (legacy_meta no es queryable directo)
    return (
        stmt,
        proyectar,
        headers,
        excel_row,
        formats,
        # post_filter:
        (lambda d: proveedor_id is None or d.get("proveedor_id") == proveedor_id)
        if proveedor_id
        else None,
    )


def _query_movimientos_tipo(
    session: Session, *, tipo: TipoMovimientoEnum
):
    desde, hasta = _resolve_range()
    sucursal_id = _resolve_sucursal_filter()
    cliente_id = request.args.get("cliente_id", type=int)
    proveedor_id = request.args.get("proveedor_id", type=int)
    medio = request.args.get("medio")

    stmt = (
        select(MovimientoCaja, Sucursal, Cliente, Proveedor, Factura)
        .join(Sucursal, Sucursal.id == MovimientoCaja.sucursal_id)
        .outerjoin(Cliente, Cliente.id == MovimientoCaja.cliente_id)
        .outerjoin(Proveedor, Proveedor.id == MovimientoCaja.proveedor_id)
        .outerjoin(Factura, Factura.id == MovimientoCaja.factura_id)
        .where(
            MovimientoCaja.fecha >= desde,
            MovimientoCaja.fecha <= hasta,
            MovimientoCaja.tipo == tipo,
        )
    )
    if sucursal_id:
        stmt = stmt.where(MovimientoCaja.sucursal_id == sucursal_id)
    if cliente_id:
        stmt = stmt.where(MovimientoCaja.cliente_id == cliente_id)
    if proveedor_id:
        stmt = stmt.where(MovimientoCaja.proveedor_id == proveedor_id)
    if medio:
        try:
            stmt = stmt.where(MovimientoCaja.medio == MedioPagoEnum(medio))
        except ValueError:
            pass
    stmt = stmt.order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc())
    return stmt


def _make_mov_proyectar(party: str):
    def proyectar(quin) -> dict[str, Any]:
        m, s, c, p, f = quin
        fecha_dia = m.fecha.date() if isinstance(m.fecha, datetime) else m.fecha
        return {
            "id": m.id,
            "fecha": fecha_dia.isoformat(),
            "monto": str(_decimal(m.monto)),
            "medio": m.medio.value if m.medio else "",
            "sucursal": f"{s.codigo} - {s.nombre}",
            "cliente": c.razon_social if c else "",
            "proveedor": p.razon_social if p else "",
            "factura_ref": (
                f"{f.tipo.value} {f.punto_venta:04d}-{f.numero:08d}" if f else ""
            ),
            "descripcion": m.descripcion or "",
        }

    return proyectar


def _query_cobranzas(session: Session, *, for_excel: bool):
    stmt = _query_movimientos_tipo(session, tipo=TipoMovimientoEnum.cobranza)
    proyectar = _make_mov_proyectar("cliente")
    headers = [
        "Fecha",
        "Cliente",
        "Factura ref.",
        "Monto",
        "Medio",
        "Sucursal",
        "Descripción",
    ]

    def excel_row(d: dict[str, Any]) -> list[Any]:
        return [
            date.fromisoformat(d["fecha"]),
            d["cliente"],
            d["factura_ref"],
            float(_decimal(d["monto"])),
            d["medio"],
            d["sucursal"],
            d["descripcion"],
        ]

    formats = {1: "date", 4: "currency"}
    return stmt, proyectar, headers, excel_row, formats


def _query_pagos(session: Session, *, for_excel: bool):
    stmt = _query_movimientos_tipo(session, tipo=TipoMovimientoEnum.pago_proveedor)
    proyectar = _make_mov_proyectar("proveedor")
    headers = [
        "Fecha",
        "Proveedor",
        "Factura ref.",
        "Monto",
        "Medio",
        "Sucursal",
        "Descripción",
    ]

    def excel_row(d: dict[str, Any]) -> list[Any]:
        return [
            date.fromisoformat(d["fecha"]),
            d["proveedor"],
            d["factura_ref"],
            float(_decimal(d["monto"])),
            d["medio"],
            d["sucursal"],
            d["descripcion"],
        ]

    formats = {1: "date", 4: "currency"}
    return stmt, proyectar, headers, excel_row, formats


def _query_movimientos_all(session: Session, *, for_excel: bool):
    desde, hasta = _resolve_range()
    sucursal_id = _resolve_sucursal_filter()
    tipo_raw = request.args.get("tipo")

    stmt = (
        select(MovimientoCaja, Sucursal, Cliente, Proveedor, Factura)
        .join(Sucursal, Sucursal.id == MovimientoCaja.sucursal_id)
        .outerjoin(Cliente, Cliente.id == MovimientoCaja.cliente_id)
        .outerjoin(Proveedor, Proveedor.id == MovimientoCaja.proveedor_id)
        .outerjoin(Factura, Factura.id == MovimientoCaja.factura_id)
        .where(
            MovimientoCaja.fecha >= desde,
            MovimientoCaja.fecha <= hasta,
        )
    )
    if sucursal_id:
        stmt = stmt.where(MovimientoCaja.sucursal_id == sucursal_id)
    if tipo_raw:
        try:
            stmt = stmt.where(MovimientoCaja.tipo == TipoMovimientoEnum(tipo_raw))
        except ValueError:
            pass
    stmt = stmt.order_by(MovimientoCaja.fecha.desc(), MovimientoCaja.id.desc())

    def proyectar(quin) -> dict[str, Any]:
        m, s, c, p, f = quin
        fecha_dia = m.fecha.date() if isinstance(m.fecha, datetime) else m.fecha
        return {
            "id": m.id,
            "fecha": fecha_dia.isoformat(),
            "tipo": m.tipo.value,
            "monto": str(_decimal(m.monto)),
            "medio": m.medio.value if m.medio else "",
            "sucursal": f"{s.codigo} - {s.nombre}",
            "cliente": c.razon_social if c else "",
            "proveedor": p.razon_social if p else "",
            "factura_ref": (
                f"{f.tipo.value} {f.punto_venta:04d}-{f.numero:08d}" if f else ""
            ),
            "descripcion": m.descripcion or "",
        }

    headers = [
        "Fecha",
        "Tipo",
        "Monto",
        "Medio",
        "Sucursal",
        "Cliente",
        "Proveedor",
        "Factura ref.",
        "Descripción",
    ]

    def excel_row(d: dict[str, Any]) -> list[Any]:
        return [
            date.fromisoformat(d["fecha"]),
            d["tipo"],
            float(_decimal(d["monto"])),
            d["medio"],
            d["sucursal"],
            d["cliente"],
            d["proveedor"],
            d["factura_ref"],
            d["descripcion"],
        ]

    formats = {1: "date", 3: "currency"}
    return stmt, proyectar, headers, excel_row, formats


def _query_stock_bajo(session: Session, *, for_excel: bool):
    sucursal_id = _resolve_sucursal_filter()
    minimo_raw = request.args.get("minimo", default=5, type=int)
    minimo = max(0, int(minimo_raw or 0))

    stmt = (
        select(StockSucursal, Articulo, Sucursal)
        .join(Articulo, Articulo.id == StockSucursal.articulo_id)
        .join(Sucursal, Sucursal.id == StockSucursal.sucursal_id)
        .where(
            Articulo.activo.is_(True),
            Articulo.controla_stock.is_(True),
            StockSucursal.cantidad < minimo,
        )
    )
    if sucursal_id:
        stmt = stmt.where(StockSucursal.sucursal_id == sucursal_id)
    stmt = stmt.order_by(StockSucursal.cantidad, Articulo.codigo)

    def proyectar(triple) -> dict[str, Any]:
        st, a, s = triple
        return {
            "articulo_id": a.id,
            "codigo": a.codigo,
            "descripcion": a.descripcion,
            "sucursal": f"{s.codigo} - {s.nombre}",
            "cantidad": str(_decimal(st.cantidad)),
            "costo": str(_decimal(a.costo)),
            "valor": str(_decimal(st.cantidad) * _decimal(a.costo)),
        }

    headers = ["Código", "Descripción", "Sucursal", "Cantidad", "Costo", "Valor"]

    def excel_row(d: dict[str, Any]) -> list[Any]:
        return [
            d["codigo"],
            d["descripcion"],
            d["sucursal"],
            float(_decimal(d["cantidad"])),
            float(_decimal(d["costo"])),
            float(_decimal(d["valor"])),
        ]

    formats = {5: "currency", 6: "currency"}
    return stmt, proyectar, headers, excel_row, formats


def _query_caes(session: Session, *, for_excel: bool):
    desde, hasta = _resolve_range()

    stmt = (
        select(Cae, Factura, Sucursal)
        .join(Factura, Factura.id == Cae.factura_id)
        .join(Sucursal, Sucursal.id == Factura.sucursal_id)
        .where(
            Cae.fecha_emision >= desde,
            Cae.fecha_emision <= hasta,
        )
        .order_by(Cae.fecha_emision.desc(), Cae.id.desc())
    )

    def proyectar(triple) -> dict[str, Any]:
        c, f, s = triple
        fecha_em = (
            c.fecha_emision.date() if isinstance(c.fecha_emision, datetime) else c.fecha_emision
        )
        return {
            "id": c.id,
            "fecha_emision": fecha_em.isoformat(),
            "cae": c.cae,
            "tipo_afip": c.tipo_afip,
            "punto_venta": c.punto_venta,
            "numero": c.numero,
            "fecha_vencimiento": c.fecha_vencimiento.isoformat(),
            "resultado": c.resultado,
            "proveedor": c.proveedor,
            "sucursal": f"{s.codigo} - {s.nombre}",
            "factura_id": f.id,
            "factura_total": str(_decimal(f.total)),
        }

    headers = [
        "Fecha emisión",
        "CAE",
        "Tipo AFIP",
        "Comprobante",
        "Vencimiento",
        "Resultado",
        "Proveedor",
        "Sucursal",
        "Total factura",
    ]

    def excel_row(d: dict[str, Any]) -> list[Any]:
        return [
            date.fromisoformat(d["fecha_emision"]),
            d["cae"],
            int(d["tipo_afip"]),
            f"{int(d['punto_venta']):04d}-{int(d['numero']):08d}",
            date.fromisoformat(d["fecha_vencimiento"]),
            d["resultado"],
            d["proveedor"],
            d["sucursal"],
            float(_decimal(d["factura_total"])),
        ]

    formats = {1: "date", 5: "date", 9: "currency"}
    return stmt, proyectar, headers, excel_row, formats


def _query_alertas(session: Session, *, for_excel: bool):
    estado_raw = request.args.get("estado")
    severidad_raw = request.args.get("severidad")
    tipo_raw = request.args.get("tipo")

    stmt = (
        select(Alerta, Factura, Sucursal)
        .outerjoin(Factura, Factura.id == Alerta.factura_id)
        .outerjoin(Sucursal, Sucursal.id == Alerta.sucursal_id)
    )
    if estado_raw:
        try:
            stmt = stmt.where(Alerta.estado == EstadoAlertaEnum(estado_raw))
        except ValueError:
            pass
    if severidad_raw:
        try:
            stmt = stmt.where(Alerta.severidad == SeveridadEnum(severidad_raw))
        except ValueError:
            pass
    if tipo_raw:
        try:
            stmt = stmt.where(Alerta.tipo == TipoAlertaEnum(tipo_raw))
        except ValueError:
            pass
    stmt = stmt.order_by(Alerta.detected_at.desc(), Alerta.id.desc())

    def proyectar(triple) -> dict[str, Any]:
        a, f, s = triple
        return {
            "id": a.id,
            "tipo": a.tipo.value,
            "severidad": a.severidad.value,
            "estado": a.estado.value,
            "titulo": a.titulo,
            "descripcion": a.descripcion,
            "detected_at": a.detected_at.isoformat() if a.detected_at else None,
            "sucursal": f"{s.codigo} - {s.nombre}" if s else "",
            "factura_ref": (
                f"{f.tipo.value} {f.punto_venta:04d}-{f.numero:08d}" if f else ""
            ),
        }

    headers = [
        "Detectada",
        "Tipo",
        "Severidad",
        "Estado",
        "Título",
        "Descripción",
        "Sucursal",
        "Factura ref.",
    ]

    def excel_row(d: dict[str, Any]) -> list[Any]:
        det = d["detected_at"]
        return [
            det[:10] if det else "",
            d["tipo"],
            d["severidad"],
            d["estado"],
            d["titulo"],
            d["descripcion"],
            d["sucursal"],
            d["factura_ref"],
        ]

    return stmt, proyectar, headers, excel_row, {}


# Mapa entidad → builder.
ENTIDADES: dict[str, Callable[[Session, bool], Any]] = {
    "clientes": _query_clientes,
    "proveedores": _query_proveedores,
    "articulos": _query_articulos,
    "ventas": _query_ventas,
    "compras": _query_compras,
    "cobranzas": _query_cobranzas,
    "pagos": _query_pagos,
    "movimientos": _query_movimientos_all,
    "stock-bajo": _query_stock_bajo,
    "caes": _query_caes,
    "alertas": _query_alertas,
}


# --- Endpoints ---------------------------------------------------------------


def _execute_listing(entidad: str) -> tuple[list[dict[str, Any]], int, list[str], Callable, dict[int, str]]:
    """Ejecuta la query y devuelve TODAS las filas proyectadas (para el .xlsx) + total."""
    builder = ENTIDADES.get(entidad)
    if builder is None:
        return [], 0, [], lambda d: [], {}
    result = builder(db.session, for_excel=True)
    # Algunos builders devuelven 5 elementos, compras devuelve 6 (con post_filter)
    post_filter = None
    if len(result) == 6:
        stmt, proyectar, headers, excel_row, formats, post_filter = result
    else:
        stmt, proyectar, headers, excel_row, formats = result
    rows_raw = db.session.execute(stmt).all()
    rows: list[dict[str, Any]] = []
    for r in rows_raw:
        # SQLAlchemy Row puede ser un único objeto o tupla
        d = proyectar(r if len(r) > 1 else r[0])
        if post_filter and not post_filter(d):
            continue
        rows.append(d)
    return rows, len(rows), headers, excel_row, formats


@bp.get("/<entidad>")
@roles_required("admin", "supervisor", "contador", "cajero")
def listar(entidad: str):
    builder = ENTIDADES.get(entidad)
    if builder is None:
        return error_response(f"entidad desconocida: {entidad}", 404, "not_found")

    page, per_page = _get_page_params()
    result = builder(db.session, for_excel=False)
    post_filter = None
    if len(result) == 6:
        stmt, proyectar, _headers, _excel_row, _formats, post_filter = result
    else:
        stmt, proyectar, _headers, _excel_row, _formats = result

    if post_filter is not None:
        # Necesitamos materializar todo y aplicar el filtro post-proyección.
        rows_raw = db.session.execute(stmt).all()
        items = []
        for r in rows_raw:
            d = proyectar(r if len(r) > 1 else r[0])
            if post_filter(d):
                items.append(d)
        total = len(items)
        offset = (page - 1) * per_page
        page_items = items[offset : offset + per_page]
    else:
        # Conteo eficiente
        from sqlalchemy import func as _func

        total = db.session.scalar(
            select(_func.count()).select_from(stmt.subquery())
        ) or 0
        rows = (
            db.session.execute(stmt.offset((page - 1) * per_page).limit(per_page)).all()
        )
        page_items = [proyectar(r if len(r) > 1 else r[0]) for r in rows]

    return jsonify(
        {
            "items": page_items,
            "page": page,
            "per_page": per_page,
            "total": int(total),
            "pages": ceil(total / per_page) if per_page else 0,
            "entidad": entidad,
        }
    )


@bp.get("/<entidad>.xlsx")
@roles_required("admin", "supervisor", "contador")
def exportar(entidad: str):
    builder = ENTIDADES.get(entidad)
    if builder is None:
        return error_response(f"entidad desconocida: {entidad}", 404, "not_found")

    rows, _total, headers, excel_row, formats = _execute_listing(entidad)
    excel_rows = [excel_row(d) for d in rows]
    title_map = {
        "clientes": "Clientes",
        "proveedores": "Proveedores",
        "articulos": "Artículos",
        "ventas": "Ventas",
        "compras": "Compras",
        "cobranzas": "Cobranzas",
        "pagos": "Pagos",
        "movimientos": "Movimientos",
        "stock-bajo": "Stock bajo",
        "caes": "CAEs",
        "alertas": "Alertas",
    }
    title = title_map.get(entidad, entidad.title())
    data = build_generic_export(title, headers, excel_rows, formats)
    filename = make_filename(f"consulta-{entidad}")
    return _xlsx_response(data, filename)
