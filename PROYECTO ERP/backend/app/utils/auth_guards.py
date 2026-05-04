"""Decoradores para validación de rol JWT."""
from __future__ import annotations

from collections.abc import Iterable
from functools import wraps

from flask_jwt_extended import get_jwt, jwt_required

from .errors import error_response


def roles_required(*allowed_roles: str):
    """Requiere JWT válido y que el claim 'rol' sea uno de los permitidos."""

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            rol = claims.get("rol")
            if rol not in allowed_roles:
                return error_response(
                    f"rol '{rol}' no autorizado", status=403, code="forbidden"
                )
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def any_role(roles: Iterable[str]):
    return roles_required(*roles)
