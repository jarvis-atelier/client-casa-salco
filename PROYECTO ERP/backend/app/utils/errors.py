"""Helpers de error handling — respuestas JSON consistentes."""
from __future__ import annotations

from typing import Any

from flask import Flask, jsonify
from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException


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
        return error_response(
            err.description or err.name,
            status=err.code or 500,
            code=err.name.lower().replace(" ", "_") if err.name else None,
        )
