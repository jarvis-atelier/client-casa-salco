"""Market basket analysis (Apriori) sobre facturas.

Devuelve reglas de asociación: dado un set de productos antecedentes, la
probabilidad de que aparezcan ciertos consecuentes en la misma transacción.

Métricas estándar:
- Soporte (support): fracción de transacciones que contiene el itemset.
- Confianza (confidence): P(consecuente | antecedente).
- Lift: cuánto más probable es ver el consecuente cuando ya está el antecedente
  versus su probabilidad incondicional. Lift > 1 = asociación positiva.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules
from mlxtend.preprocessing import TransactionEncoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.articulo import Articulo
from app.models.factura import EstadoComprobanteEnum, Factura
from app.models.factura_item import FacturaItem


def _resolve_window(
    fecha_desde: date | None, fecha_hasta: date | None
) -> tuple[datetime, datetime]:
    hasta = fecha_hasta or date.today()
    desde = fecha_desde or (hasta - timedelta(days=90))
    return (
        datetime.combine(desde, datetime.min.time()),
        datetime.combine(hasta, datetime.max.time()),
    )


def calcular_correlaciones(
    session: Session,
    *,
    fecha_desde: date | None = None,
    fecha_hasta: date | None = None,
    sucursal_id: int | None = None,
    soporte_min: float = 0.01,
    confianza_min: float = 0.3,
    lift_min: float = 1.5,
    top_n: int = 50,
    max_len: int = 3,
) -> dict:
    """Corre Apriori + association_rules sobre las facturas del período.

    Args:
        session: Session SQLAlchemy.
        fecha_desde / fecha_hasta: rango de fechas. Default: últimos 90 días.
        sucursal_id: opcional, filtra una sucursal.
        soporte_min: soporte mínimo del itemset (0..1). Por defecto 0.01 (1%).
        confianza_min: confianza mínima de la regla (0..1). Por defecto 0.30.
        lift_min: lift mínimo. Por defecto 1.5 (asociaciones realmente positivas).
        top_n: cantidad máxima de reglas a devolver, ordenadas por lift desc.
        max_len: longitud máxima del itemset (suma de antecedente+consecuente).

    Returns:
        dict con:
            transacciones_analizadas: int
            items_unicos: int
            fecha_desde / fecha_hasta: ISO date
            sucursal_id: int | None
            params: dict con los thresholds usados
            reglas: list[dict] con cada regla
    """
    desde, hasta = _resolve_window(fecha_desde, fecha_hasta)

    # 1. Cargar items de facturas tipo venta emitidas en el período.
    where = [
        Factura.fecha >= desde,
        Factura.fecha <= hasta,
        Factura.estado == EstadoComprobanteEnum.emitida,
    ]
    if sucursal_id is not None:
        where.append(Factura.sucursal_id == sucursal_id)

    stmt = (
        select(FacturaItem.factura_id, FacturaItem.articulo_id)
        .select_from(FacturaItem)
        .join(Factura, Factura.id == FacturaItem.factura_id)
        .where(*where)
    )
    rows = session.execute(stmt).all()

    if not rows:
        return _empty_result(desde, hasta, sucursal_id, soporte_min, confianza_min, lift_min)

    # 2. Armar transacciones (set de articulo_id por factura).
    # Casteamos los IDs a string porque mlxtend + pandas sparse tiene un bug
    # con nombres de columna numéricos.
    by_factura: dict[int, set[str]] = {}
    for factura_id, articulo_id in rows:
        by_factura.setdefault(factura_id, set()).add(str(int(articulo_id)))

    # Filtrar transacciones con menos de 2 items — no contribuyen a reglas.
    transacciones = [list(items) for items in by_factura.values() if len(items) >= 2]
    n_trans = len(transacciones)
    items_unicos: set[str] = set()
    for t in transacciones:
        items_unicos.update(t)

    if n_trans < 5:
        return _empty_result(
            desde,
            hasta,
            sucursal_id,
            soporte_min,
            confianza_min,
            lift_min,
            transacciones_analizadas=n_trans,
            items_unicos=len(items_unicos),
        )

    # 3. One-hot encoding sparse via TransactionEncoder.
    te = TransactionEncoder()
    te_array = te.fit_transform(transacciones, sparse=True)
    df = pd.DataFrame.sparse.from_spmatrix(te_array, columns=te.columns_)

    # 4. Apriori. low_memory=True para datasets más grandes.
    try:
        frequent = apriori(
            df,
            min_support=soporte_min,
            use_colnames=True,
            low_memory=True,
            max_len=max_len,
        )
    except (ValueError, MemoryError):
        return _empty_result(
            desde,
            hasta,
            sucursal_id,
            soporte_min,
            confianza_min,
            lift_min,
            transacciones_analizadas=n_trans,
            items_unicos=len(items_unicos),
        )

    if frequent.empty:
        return _empty_result(
            desde,
            hasta,
            sucursal_id,
            soporte_min,
            confianza_min,
            lift_min,
            transacciones_analizadas=n_trans,
            items_unicos=len(items_unicos),
        )

    # 5. association_rules — usamos confidence como métrica primaria, después
    # filtramos por lift en pandas.
    try:
        reglas_df = association_rules(
            frequent,
            metric="confidence",
            min_threshold=confianza_min,
            num_itemsets=n_trans,
        )
    except TypeError:
        # mlxtend < 0.23 no acepta num_itemsets
        reglas_df = association_rules(
            frequent, metric="confidence", min_threshold=confianza_min
        )

    if reglas_df.empty:
        return _empty_result(
            desde,
            hasta,
            sucursal_id,
            soporte_min,
            confianza_min,
            lift_min,
            transacciones_analizadas=n_trans,
            items_unicos=len(items_unicos),
        )

    reglas_df = reglas_df[reglas_df["lift"] >= lift_min]
    reglas_df = reglas_df.sort_values("lift", ascending=False).head(top_n)

    if reglas_df.empty:
        return _empty_result(
            desde,
            hasta,
            sucursal_id,
            soporte_min,
            confianza_min,
            lift_min,
            transacciones_analizadas=n_trans,
            items_unicos=len(items_unicos),
        )

    # 6. Resolver descripciones de articulos referenciados por las reglas.
    # Las columnas son strings (por el cast del paso 2); las parseamos a int
    # para resolver contra la tabla articulos.
    art_ids: set[int] = set()
    for col in ("antecedents", "consequents"):
        for fset in reglas_df[col]:
            for aid in fset:
                try:
                    art_ids.add(int(aid))
                except (TypeError, ValueError):
                    continue

    art_map: dict[int, dict] = {}
    if art_ids:
        art_stmt = select(Articulo.id, Articulo.codigo, Articulo.descripcion).where(
            Articulo.id.in_(art_ids)
        )
        for aid, codigo, descripcion in session.execute(art_stmt).all():
            art_map[int(aid)] = {"codigo": codigo, "descripcion": descripcion}

    def _to_meta(items: frozenset) -> tuple[list[str], list[str], list[int]]:
        ids = sorted(int(x) for x in items)
        codigos = [art_map.get(i, {}).get("codigo", f"#{i}") for i in ids]
        descripciones = [
            art_map.get(i, {}).get("descripcion", f"Artículo {i}") for i in ids
        ]
        return codigos, descripciones, ids

    reglas_out: list[dict] = []
    for _, r in reglas_df.iterrows():
        ant_codigos, ant_descs, ant_ids = _to_meta(r["antecedents"])
        cons_codigos, cons_descs, cons_ids = _to_meta(r["consequents"])
        reglas_out.append(
            {
                "antecedentes_ids": ant_ids,
                "antecedentes_codigos": ant_codigos,
                "antecedentes_desc": ant_descs,
                "consecuentes_ids": cons_ids,
                "consecuentes_codigos": cons_codigos,
                "consecuentes_desc": cons_descs,
                "soporte": _safe_float(r["support"]),
                "confianza": _safe_float(r["confidence"]),
                "lift": _safe_float(r["lift"]),
            }
        )

    return {
        "fecha_desde": desde.date().isoformat(),
        "fecha_hasta": hasta.date().isoformat(),
        "sucursal_id": sucursal_id,
        "transacciones_analizadas": n_trans,
        "items_unicos": len(items_unicos),
        "params": {
            "soporte_min": soporte_min,
            "confianza_min": confianza_min,
            "lift_min": lift_min,
            "top_n": top_n,
            "max_len": max_len,
        },
        "reglas": reglas_out,
    }


def _empty_result(
    desde: datetime,
    hasta: datetime,
    sucursal_id: int | None,
    soporte_min: float,
    confianza_min: float,
    lift_min: float,
    *,
    transacciones_analizadas: int = 0,
    items_unicos: int = 0,
) -> dict:
    return {
        "fecha_desde": desde.date().isoformat(),
        "fecha_hasta": hasta.date().isoformat(),
        "sucursal_id": sucursal_id,
        "transacciones_analizadas": transacciones_analizadas,
        "items_unicos": items_unicos,
        "params": {
            "soporte_min": soporte_min,
            "confianza_min": confianza_min,
            "lift_min": lift_min,
        },
        "reglas": [],
    }


def _safe_float(v) -> float:
    """Convierte numpy/pandas scalar a float python, NaN/inf → 0."""
    try:
        f = float(v)
    except (TypeError, ValueError):
        return 0.0
    if not np.isfinite(f):
        return 0.0
    return round(f, 6)
