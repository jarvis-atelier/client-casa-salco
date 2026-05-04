"""Auth helpers — password hashing (bcrypt 12 rounds) y shortcuts de JWT."""
from __future__ import annotations

import bcrypt
from flask_jwt_extended import create_access_token, create_refresh_token

from app.models.user import User

_BCRYPT_ROUNDS = 12


def hash_password(plain: str) -> str:
    """Devuelve el hash bcrypt de una contraseña (costo 12)."""
    salt = bcrypt.gensalt(rounds=_BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica un password contra su hash bcrypt."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def _user_claims(user: User) -> dict:
    return {
        "rol": user.rol.value,
        "sucursal_id": user.sucursal_id,
        "email": user.email,
    }


def issue_tokens(user: User) -> tuple[str, str]:
    """Emite (access, refresh) con claims del usuario."""
    identity = str(user.id)
    claims = _user_claims(user)
    access = create_access_token(identity=identity, additional_claims=claims)
    refresh = create_refresh_token(identity=identity, additional_claims=claims)
    return access, refresh
