"""Helper de paginación para queries SQLAlchemy."""
from __future__ import annotations

from math import ceil

from flask import request
from sqlalchemy import func, select
from sqlalchemy.orm import Query

from app.extensions import db


def get_page_params(default_per_page: int = 50, max_per_page: int = 200) -> tuple[int, int]:
    try:
        page = max(int(request.args.get("page", 1)), 1)
    except (TypeError, ValueError):
        page = 1
    # Acepta tanto `per_page` como su alias `limit` por compatibilidad con
    # consumidores legacy.
    raw = request.args.get("per_page")
    if raw is None:
        raw = request.args.get("limit")
    try:
        per_page = int(raw) if raw is not None else default_per_page
    except (TypeError, ValueError):
        per_page = default_per_page
    per_page = max(1, min(per_page, max_per_page))
    return page, per_page


def paginate_query(stmt, schema_cls, page: int, per_page: int) -> dict:
    """Pagina un `select(...)` SA 2.0 y serializa con un schema Pydantic v2."""
    total = db.session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.session.execute(stmt.offset((page - 1) * per_page).limit(per_page)).scalars().all()
    return {
        "items": [schema_cls.model_validate(r).model_dump(mode="json") for r in rows],
        "page": page,
        "per_page": per_page,
        "total": int(total),
        "pages": ceil(total / per_page) if per_page else 0,
    }


def paginate_legacy_query(query: Query, schema_cls, page: int, per_page: int) -> dict:
    """Variante para queries legacy (db.session.query())."""
    total = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [schema_cls.model_validate(r).model_dump(mode="json") for r in rows],
        "page": page,
        "per_page": per_page,
        "total": int(total),
        "pages": ceil(total / per_page) if per_page else 0,
    }
