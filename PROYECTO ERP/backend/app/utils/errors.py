"""Helpers de error handling — respuestas JSON consistentes."""
from __future__ import annotations

from typing import Any

from flask import Flask, jsonify
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException

from app.extensions import jwt


def _jsonable(obj: Any) -> Any:
    """Convierte recursivamente un objeto a algo que json.dumps pueda manejar.

    Útil para sanear `ValidationError.errors()` que a veces incluye excepciones
    o tipos custom en `ctx`.
    """
    if isinstance(obj, (str, int, float, bool)) or obj is None:
        return obj
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return str(obj)


def error_response(
    message: str,
    status: int = 400,
    code: str | None = None,
    details: dict | list | None = None,
):
    payload: dict[str, Any] = {"error": message}
    if code:
        payload["code"] = code
    if details is not None:
        payload["details"] = _jsonable(details)
    return jsonify(payload), status


def register_error_handlers(app: Flask) -> None:
    @app.errorhandler(ValidationError)
    def _validation(err: ValidationError):
        return error_response(
            "validation_error",
            status=422,
            code="validation_error",
            details=err.errors(include_url=False),
        )

    @app.errorhandler(IntegrityError)
    def _integrity(err: IntegrityError):
        return error_response(
            "integrity_error",
            status=409,
            code="integrity_error",
            details=str(err.orig) if err.orig else None,
        )

    @app.errorhandler(HTTPException)
    def _http(err: HTTPException):
        message = err.description or err.name or ""
        # Werkzeug pone un blurb largo en 404 ("...check your spelling..."),
        # no aporta nada en una API JSON.
        if err.code == 404 and "requested URL was not found" in message:
            message = "ruta no encontrada"
        return error_response(
            message or "error",
            status=err.code or 500,
            code=err.name.lower().replace(" ", "_") if err.name else None,
        )

    # Flask-JWT-Extended por defecto devuelve {"msg": "..."} — armonizamos al
    # shape {code, error} del resto de la API.
    @jwt.invalid_token_loader
    def _jwt_invalid(reason: str):
        return error_response(reason, status=422, code="invalid_token")

    @jwt.unauthorized_loader
    def _jwt_unauthorized(reason: str):
        return error_response(reason, status=401, code="unauthorized")

    @jwt.expired_token_loader
    def _jwt_expired(_jwt_header, _jwt_payload):
        return error_response("token expirado", status=401, code="token_expired")

    @jwt.revoked_token_loader
    def _jwt_revoked(_jwt_header, _jwt_payload):
        return error_response("token revocado", status=401, code="token_revoked")

    @jwt.needs_fresh_token_loader
    def _jwt_needs_fresh(_jwt_header, _jwt_payload):
        return error_response(
            "se requiere token fresh", status=401, code="fresh_token_required"
        )
