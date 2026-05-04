"""Endpoint de configuración de comercio (singleton)."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from pydantic import ValidationError

from app.extensions import db
from app.models.comercio import ComercioConfig
from app.schemas.comercio import ComercioOut, ComercioUpdate
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

bp = Blueprint("comercio", __name__, url_prefix="/api/v1/comercio")


def _get_or_create() -> ComercioConfig:
    cfg = db.session.get(ComercioConfig, 1)
    if cfg is None:
        cfg = ComercioConfig(id=1)
        db.session.add(cfg)
        db.session.commit()
    return cfg


@bp.get("")
@roles_required("admin", "supervisor", "cajero", "fiambrero", "repositor", "contador")
def get_comercio():
    cfg = _get_or_create()
    return jsonify(ComercioOut.model_validate(cfg).model_dump(mode="json"))


@bp.patch("")
@roles_required("admin")
def patch_comercio():
    try:
        payload = ComercioUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )

    cfg = _get_or_create()
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(cfg, k, v)
    db.session.commit()
    return jsonify(ComercioOut.model_validate(cfg).model_dump(mode="json"))
