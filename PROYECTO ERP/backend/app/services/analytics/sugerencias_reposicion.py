"""Sugerencias de reposición — opción C de stock inteligente.

API:

- `calcular_stock_optimo(velocidad_diaria, lead_time_dias, factor_seguridad)`
- `sugerir_reposicion(session, sucursal_id?)` → lista agrupada por proveedor
- `actualizar_stock_optimo_y_reorden_auto(session)` → job de recálculo masivo
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.articulo import Articulo
from app.models.proveedor import Proveedor
from app.models.stock import StockSucursal

from .velocidad_venta import calcular_velocidad_venta


# --- Constantes ---------------------------------------------------------------

# Lead time default si no hay nada seteado en proveedor / articulo / sucursal.
LEAD_TIME_DEFAULT_DIAS = 7

# Factor de seguridad para stock óptimo.
FACTOR_SEGURIDAD_DEFAULT = 1.5

# Si no hay punto_reorden seteado, se sugiere usar velocidad × lead_time × este
# factor (más bajo que el óptimo, pero alto suficiente para gatillar a tiempo).
FACTOR_REORDEN_DEFAULT = 1.2

ZERO = Decimal("0")
ONE = Decimal("1")


def _to_decimal(v: Any) -> Decimal:
    if v is None:
        return ZERO
    if isinstance(v, Decimal):
        return v
    return Decimal(str(v))


def _q0(v: Decimal) -> Decimal:
    """Redondea a entero (ceil-friendly half-up)."""
    return v.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


def _q4(v: Decimal) -> Decimal:
    return v.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)


# --- Cálculo puro -------------------------------------------------------------


def calcular_stock_optimo(
    velocidad_diaria: Decimal | float | int,
    lead_time_dias: int | None,
    factor_seguridad: float = FACTOR_SEGURIDAD_DEFAULT,
) -> Decimal:
    """Stock óptimo = velocidad_diaria × lead_time × factor_seguridad.

    Si `velocidad_diaria` <= 0 o `lead_time` es None/0, devuelve 0.
    Devuelve un Decimal entero (sin decimales) — son unidades.
    """
    v = _to_decimal(velocidad_diaria)
    if v <= 0:
        return ZERO
    lt = lead_time_dias if (lead_time_dias is not None and lead_time_dias > 0) else 0
    if lt == 0:
        return ZERO
    raw = v * Decimal(lt) * Decimal(str(factor_seguridad))
    return _q0(raw)


def calcular_reorden_sugerido(
    velocidad_diaria: Decimal | float | int,
    lead_time_dias: int | None,
    factor: float = FACTOR_REORDEN_DEFAULT,
) -> Decimal:
    v = _to_decimal(velocidad_diaria)
    if v <= 0:
        return ZERO
    lt = lead_time_dias if (lead_time_dias is not None and lead_time_dias > 0) else 0
    if lt == 0:
        return ZERO
    return _q0(v * Decimal(lt) * Decimal(str(factor)))


# --- Sugerencias --------------------------------------------------------------


def _urgencia(row: StockSucursal) -> str:
    """Devuelve 'critica' | 'alta' | 'media'."""
    estado = row.estado_reposicion
    if estado in ("agotado", "critico"):
        return "critica"
    if estado == "reorden":
        return "alta"
    return "media"


def _necesita_reposicion(row: StockSucursal) -> bool:
    """True si el (articulo, sucursal) está en agotado / critico / reorden."""
    return row.estado_reposicion in ("agotado", "critico", "reorden")


def sugerir_reposicion(
    session: Session,
    sucursal_id: int | None = None,
) -> dict:
    """Devuelve sugerencias de reposición agrupadas por proveedor.

    Args:
        session: SA session.
        sucursal_id: si se pasa, filtra una sola sucursal.

    Returns:
        dict {
            "totales": {sucursales, articulos_a_reponer, valor_estimado},
            "por_proveedor": [
                {
                    "proveedor": {id, codigo, razon_social, ...} | None,
                    "items": [{articulo, sucursal, cantidad_actual,
                               cantidad_a_pedir, urgencia, costo_unitario,
                               total_linea}],
                    "total_items": int,
                    "total_estimado": str,
                }
            ]
        }
    """
    stmt = (
        select(StockSucursal)
        .options(
            joinedload(StockSucursal.articulo).joinedload(Articulo.proveedor_principal),
            joinedload(StockSucursal.sucursal),
        )
    )
    if sucursal_id is not None:
        stmt = stmt.where(StockSucursal.sucursal_id == sucursal_id)

    rows = session.execute(stmt).scalars().unique().all()

    sucursales_set: set[int] = set()
    articulos_a_reponer = 0
    valor_total = ZERO

    # proveedor_id (None = "Sin proveedor") -> lista de items
    grupos: dict[int | None, list[dict[str, Any]]] = {}
    proveedor_meta: dict[int | None, dict[str, Any] | None] = {}

    for row in rows:
        if not _necesita_reposicion(row):
            continue
        articulo = row.articulo
        if articulo is None:
            continue
        if not articulo.activo:
            continue
        if not articulo.controla_stock:
            continue

        sucursales_set.add(row.sucursal_id)
        articulos_a_reponer += 1

        cantidad_actual = _to_decimal(row.cantidad)
        objetivo = _to_decimal(row.efectivo_maximo) or _to_decimal(
            row.stock_optimo_calculado
        )
        if objetivo <= 0:
            # Sin óptimo: usar reorden × 2 como fallback razonable
            ref = _to_decimal(row.efectivo_reorden)
            if ref > 0:
                objetivo = ref * Decimal("2")
            else:
                emin = _to_decimal(row.efectivo_minimo)
                objetivo = emin * Decimal("3") if emin > 0 else Decimal("10")
        cantidad_a_pedir = objetivo - cantidad_actual
        if cantidad_a_pedir <= 0:
            cantidad_a_pedir = Decimal("1")
        cantidad_a_pedir = _q0(cantidad_a_pedir)

        costo_unit = _to_decimal(articulo.costo)
        total_linea = (cantidad_a_pedir * costo_unit).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        valor_total += total_linea

        prov = articulo.proveedor_principal
        prov_id = prov.id if prov else None
        if prov_id not in proveedor_meta:
            proveedor_meta[prov_id] = (
                {
                    "id": prov.id,
                    "codigo": prov.codigo,
                    "razon_social": prov.razon_social,
                    "cuit": prov.cuit,
                    "telefono": prov.telefono,
                    "email": prov.email,
                    "lead_time_dias_default": prov.lead_time_dias_default,
                }
                if prov
                else None
            )

        item = {
            "articulo": {
                "id": articulo.id,
                "codigo": articulo.codigo,
                "descripcion": articulo.descripcion,
                "unidad_medida": articulo.unidad_medida.value
                if articulo.unidad_medida
                else "unidad",
                "costo": str(costo_unit),
                "controla_vencimiento": articulo.controla_vencimiento,
            },
            "sucursal": {
                "id": row.sucursal.id if row.sucursal else row.sucursal_id,
                "codigo": row.sucursal.codigo if row.sucursal else "",
                "nombre": row.sucursal.nombre if row.sucursal else "",
            }
            if row.sucursal
            else {"id": row.sucursal_id, "codigo": "", "nombre": ""},
            "cantidad_actual": str(cantidad_actual),
            "stock_minimo": str(_to_decimal(row.efectivo_minimo)),
            "punto_reorden": str(_to_decimal(row.efectivo_reorden)),
            "stock_maximo": str(_to_decimal(row.efectivo_maximo)),
            "cantidad_a_pedir": str(cantidad_a_pedir),
            "costo_unitario": str(costo_unit),
            "total_linea": str(total_linea),
            "urgencia": _urgencia(row),
            "estado": row.estado_reposicion,
        }
        grupos.setdefault(prov_id, []).append(item)

    por_proveedor: list[dict[str, Any]] = []
    for prov_id, items in grupos.items():
        # Ordenar items por urgencia (critica -> alta -> media), luego cantidad
        urg_rank = {"critica": 0, "alta": 1, "media": 2}
        items.sort(key=lambda i: (urg_rank.get(i["urgencia"], 9), i["articulo"]["codigo"]))
        total_grupo = sum(
            (Decimal(i["total_linea"]) for i in items), Decimal("0")
        )
        por_proveedor.append(
            {
                "proveedor": proveedor_meta[prov_id],
                "items": items,
                "total_items": len(items),
                "total_estimado": str(total_grupo.quantize(Decimal("0.01"))),
            }
        )

    # Orden grupos: por valor estimado desc
    por_proveedor.sort(
        key=lambda g: Decimal(g["total_estimado"]), reverse=True
    )

    return {
        "totales": {
            "sucursales": len(sucursales_set),
            "articulos_a_reponer": articulos_a_reponer,
            "valor_estimado": str(valor_total.quantize(Decimal("0.01"))),
        },
        "por_proveedor": por_proveedor,
    }


def actualizar_stock_optimo_y_reorden_auto(
    session: Session,
    sucursal_id: int | None = None,
    factor_seguridad: float = FACTOR_SEGURIDAD_DEFAULT,
    dias_velocidad: int = 30,
) -> dict:
    """Job: recalcula stock_optimo_calculado para cada (articulo, sucursal).

    Y si el `punto_reorden` (sucursal o default articulo) está vacío, sugiere
    `velocidad × lead_time × FACTOR_REORDEN_DEFAULT` y lo guarda en el
    `punto_reorden` del row de sucursal (sin tocar el default del artículo).

    Args:
        session: SA session.
        sucursal_id: si se pasa, recalcula sólo esa sucursal.
        factor_seguridad: para el óptimo.
        dias_velocidad: ventana de cálculo.

    Returns:
        dict con counts: {filas_recalculadas, reorden_seteado, sin_velocidad}.
    """
    stmt = select(StockSucursal).options(
        joinedload(StockSucursal.articulo).joinedload(Articulo.proveedor_principal),
    )
    if sucursal_id is not None:
        stmt = stmt.where(StockSucursal.sucursal_id == sucursal_id)
    rows = session.execute(stmt).scalars().unique().all()

    filas_recalc = 0
    reorden_seteado = 0
    sin_velocidad = 0
    ahora = datetime.now(timezone.utc)

    for row in rows:
        articulo = row.articulo
        if articulo is None or not articulo.controla_stock:
            continue

        velocidad = calcular_velocidad_venta(
            session, articulo.id, row.sucursal_id, dias=dias_velocidad
        )
        v_diaria = velocidad["velocidad_promedio_diaria"]

        lead_time = row.efectivo_lead_time or LEAD_TIME_DEFAULT_DIAS

        if v_diaria <= 0:
            sin_velocidad += 1
            row.ultima_recalculacion = ahora
            continue

        optimo = calcular_stock_optimo(v_diaria, lead_time, factor_seguridad)
        row.stock_optimo_calculado = optimo
        row.ultima_recalculacion = ahora
        filas_recalc += 1

        # Si NO hay reorden ni en sucursal ni en default del articulo, lo seteamos
        # en la sucursal (no tocamos el default global del articulo).
        if (
            row.punto_reorden is None
            and articulo.punto_reorden_default is None
        ):
            row.punto_reorden = calcular_reorden_sugerido(v_diaria, lead_time)
            reorden_seteado += 1

    session.commit()
    return {
        "filas_recalculadas": filas_recalc,
        "reorden_seteado": reorden_seteado,
        "sin_velocidad": sin_velocidad,
    }


__all__ = [
    "FACTOR_SEGURIDAD_DEFAULT",
    "FACTOR_REORDEN_DEFAULT",
    "LEAD_TIME_DEFAULT_DIAS",
    "actualizar_stock_optimo_y_reorden_auto",
    "calcular_reorden_sugerido",
    "calcular_stock_optimo",
    "sugerir_reposicion",
]
