"""Endpoints de reposición — opción C de stock inteligente.

- GET  /api/v1/reposicion?sucursal_id=  → lista agrupada por proveedor.
- POST /api/v1/reposicion/orden-compra  → crea factura tipo C en estado
  borrador con los items pasados (precio costo, IVA 21).
- POST /api/v1/reposicion/recalcular    → admin-only. Recalcula stock_optimo
  y reorden auto para todas las (articulo, sucursal).
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt_identity
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select

from app.extensions import db
from app.models.articulo import Articulo
from app.models.factura import (
    EstadoComprobanteEnum,
    Factura,
    TipoComprobanteEnum,
)
from app.models.factura_item import FacturaItem
from app.models.proveedor import Proveedor
from app.models.sucursal import Sucursal
from app.services.analytics.sugerencias_reposicion import (
    actualizar_stock_optimo_y_reorden_auto,
    sugerir_reposicion,
)
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

bp = Blueprint("reposicion", __name__, url_prefix="/api/v1/reposicion")


Q01 = Decimal("0.01")
Q4 = Decimal("0.0001")


def _q01(v: Decimal) -> Decimal:
    return v.quantize(Q01, rounding=ROUND_HALF_UP)


def _q4(v: Decimal) -> Decimal:
    return v.quantize(Q4, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# GET /reposicion — lista agrupada por proveedor
# ---------------------------------------------------------------------------


@bp.get("")
@roles_required("admin", "supervisor", "contador")
def get_reposicion():
    sucursal_id = request.args.get("sucursal_id", type=int)
    if sucursal_id is not None:
        sucursal = db.session.get(Sucursal, sucursal_id)
        if sucursal is None or sucursal.deleted_at is not None:
            return error_response("sucursal no encontrada", 404, "not_found")

    result = sugerir_reposicion(db.session, sucursal_id=sucursal_id)
    return jsonify(result)


# ---------------------------------------------------------------------------
# POST /reposicion/orden-compra — crea factura tipo C borrador
# ---------------------------------------------------------------------------


class _OrdenItem(BaseModel):
    articulo_id: int
    cantidad: Decimal = Field(gt=0)
    costo_unitario: Decimal | None = Field(default=None, ge=0)


class _OrdenRequest(BaseModel):
    proveedor_id: int | None = None
    sucursal_id: int
    items: list[_OrdenItem] = Field(min_length=1)
    fecha_estimada_recepcion: str | None = None  # ISO date opcional
    observacion: str | None = None


def _next_numero(
    session, sucursal_id: int, punto_venta: int, tipo: TipoComprobanteEnum
) -> int:
    actual = session.scalar(
        select(func.coalesce(func.max(Factura.numero), 0))
        .where(Factura.sucursal_id == sucursal_id)
        .where(Factura.punto_venta == punto_venta)
        .where(Factura.tipo == tipo)
    )
    return int(actual or 0) + 1


@bp.post("/orden-compra")
@roles_required("admin", "supervisor")
def crear_orden_compra():
    """Genera una OC como Factura tipo C en estado borrador.

    Cada item usa el `costo_unitario` indicado o, si no se pasa, el costo
    base del articulo. IVA 21% por defecto.
    """
    try:
        payload = _OrdenRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )

    sucursal = db.session.get(Sucursal, payload.sucursal_id)
    if sucursal is None or sucursal.deleted_at is not None:
        return error_response("sucursal no encontrada", 404, "not_found")

    proveedor = None
    if payload.proveedor_id is not None:
        proveedor = db.session.get(Proveedor, payload.proveedor_id)
        if proveedor is None or proveedor.deleted_at is not None:
            return error_response("proveedor no encontrado", 404, "not_found")

    try:
        user_id = int(get_jwt_identity())
    except (TypeError, ValueError):
        return error_response("usuario no identificado", 401, "unauthorized")

    # Cargar artículos
    art_ids = [it.articulo_id for it in payload.items]
    arts = (
        db.session.execute(
            select(Articulo).where(Articulo.id.in_(art_ids))
        )
        .scalars()
        .all()
    )
    art_by_id = {a.id: a for a in arts}
    for it in payload.items:
        if it.articulo_id not in art_by_id:
            return error_response(
                f"articulo {it.articulo_id} no existe", 404, "not_found"
            )

    ahora = datetime.now(UTC)
    punto_venta = 1
    tipo = TipoComprobanteEnum.factura_c
    numero = _next_numero(db.session, sucursal.id, punto_venta, tipo)

    obs_partes: list[str] = ["Orden de compra (reposición)"]
    if proveedor:
        obs_partes.append(f"Proveedor: {proveedor.razon_social}")
    if payload.fecha_estimada_recepcion:
        obs_partes.append(f"Recepción estimada: {payload.fecha_estimada_recepcion}")
    if payload.observacion:
        obs_partes.append(payload.observacion)
    observacion = " · ".join(obs_partes)

    factura = Factura(
        sucursal_id=sucursal.id,
        punto_venta=punto_venta,
        tipo=tipo,
        numero=numero,
        fecha=ahora,
        cliente_id=None,
        cajero_id=user_id,
        estado=EstadoComprobanteEnum.borrador,
        subtotal=Decimal("0"),
        total_iva=Decimal("0"),
        total_descuento=Decimal("0"),
        total=Decimal("0"),
        moneda="ARS",
        cotizacion=Decimal("1"),
        observacion=observacion,
        legacy_meta={
            "kind": "orden_compra_reposicion",
            "proveedor_id": payload.proveedor_id,
            "fecha_estimada_recepcion": payload.fecha_estimada_recepcion,
        },
    )
    db.session.add(factura)
    db.session.flush()

    subtotal_acc = Decimal("0")
    iva_acc = Decimal("0")
    total_acc = Decimal("0")

    for orden, it in enumerate(payload.items):
        art = art_by_id[it.articulo_id]
        costo = (
            it.costo_unitario
            if it.costo_unitario is not None
            else (art.costo or Decimal("0"))
        )
        cantidad = it.cantidad
        iva_porc = art.iva_porc or Decimal("21")

        line_subtotal = _q4(cantidad * costo)
        line_iva = _q4(line_subtotal * iva_porc / Decimal("100"))
        line_total = _q4(line_subtotal + line_iva)

        db.session.add(
            FacturaItem(
                factura_id=factura.id,
                articulo_id=art.id,
                codigo=art.codigo,
                descripcion=art.descripcion,
                cantidad=cantidad,
                precio_unitario=costo,
                descuento_porc=Decimal("0"),
                iva_porc=iva_porc,
                iva_monto=line_iva,
                subtotal=line_subtotal,
                total=line_total,
                orden=orden,
            )
        )

        subtotal_acc += line_subtotal
        iva_acc += line_iva
        total_acc += line_total

    factura.subtotal = _q01(subtotal_acc)
    factura.total_iva = _q01(iva_acc)
    factura.total = _q01(total_acc)
    db.session.commit()

    return (
        jsonify(
            {
                "id": factura.id,
                "tipo": factura.tipo.value,
                "numero": factura.numero,
                "punto_venta": factura.punto_venta,
                "estado": factura.estado.value,
                "sucursal_id": factura.sucursal_id,
                "subtotal": str(factura.subtotal),
                "total_iva": str(factura.total_iva),
                "total": str(factura.total),
                "items_count": len(payload.items),
                "proveedor_id": payload.proveedor_id,
                "fecha_estimada_recepcion": payload.fecha_estimada_recepcion,
                "created_at": factura.created_at.isoformat()
                if factura.created_at
                else None,
            }
        ),
        201,
    )


# ---------------------------------------------------------------------------
# POST /reposicion/recalcular — admin only, dispara job de recálculo
# ---------------------------------------------------------------------------


@bp.post("/recalcular")
@roles_required("admin")
def recalcular():
    sucursal_id = request.args.get("sucursal_id", type=int)
    result = actualizar_stock_optimo_y_reorden_auto(
        db.session, sucursal_id=sucursal_id
    )
    return jsonify(result)
