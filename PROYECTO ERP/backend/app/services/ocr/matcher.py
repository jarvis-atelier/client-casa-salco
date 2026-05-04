"""Matching heurístico de proveedor y artículos para OCR.

La idea es sugerir un match para que el usuario revise antes de confirmar.
- Proveedor: por CUIT exacto > por razón social LIKE.
- Artículo: por descripción LIKE (case-insensitive).
"""
from __future__ import annotations

import re
from typing import Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.articulo import Articulo
from app.models.proveedor import Proveedor


def _normalizar_cuit(raw: str | None) -> str | None:
    if not raw:
        return None
    digits = re.sub(r"\D", "", raw)
    if len(digits) != 11:
        return None
    return f"{digits[:2]}-{digits[2:10]}-{digits[10]}"


def match_proveedor(
    session: Session,
    razon_social: str | None,
    cuit: str | None,
) -> Proveedor | None:
    cuit_norm = _normalizar_cuit(cuit)
    if cuit_norm:
        prov = session.execute(
            select(Proveedor).where(
                Proveedor.deleted_at.is_(None),
                or_(
                    Proveedor.cuit == cuit_norm,
                    Proveedor.cuit == cuit_norm.replace("-", ""),
                ),
            )
        ).scalar_one_or_none()
        if prov is not None:
            return prov

    if razon_social:
        # Tomamos las primeras 3 palabras significativas para LIKE.
        palabras = [p for p in razon_social.split() if len(p) >= 3][:3]
        if palabras:
            cond = [Proveedor.razon_social.ilike(f"%{p}%") for p in palabras]
            prov = session.execute(
                select(Proveedor)
                .where(Proveedor.deleted_at.is_(None), *cond)
                .limit(1)
            ).scalar_one_or_none()
            if prov is not None:
                return prov

    return None


def match_articulo(
    session: Session,
    descripcion: str,
) -> Articulo | None:
    """Heurística simple: palabras significativas con AND."""
    if not descripcion:
        return None
    palabras = [p for p in descripcion.split() if len(p) >= 3][:3]
    if not palabras:
        return None
    cond = [Articulo.descripcion.ilike(f"%{p}%") for p in palabras]
    art = session.execute(
        select(Articulo)
        .where(
            Articulo.deleted_at.is_(None),
            Articulo.activo.is_(True),
            *cond,
        )
        .order_by(Articulo.id.asc())
        .limit(1)
    ).scalar_one_or_none()
    return art


def enriquecer_items_con_match(
    session: Session,
    items_raw: Iterable[dict],
) -> list[dict]:
    """Devuelve la misma lista pero agregando `articulo_id_match` cuando hay."""
    enriched = []
    for it in items_raw:
        match = match_articulo(session, it.get("descripcion", ""))
        new = dict(it)
        new["articulo_id_match"] = match.id if match is not None else None
        enriched.append(new)
    return enriched
