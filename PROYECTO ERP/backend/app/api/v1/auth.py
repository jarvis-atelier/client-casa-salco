"""Blueprint de autenticación — login/refresh/me/register/users."""
from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from pydantic import ValidationError
from sqlalchemy import select

from app.extensions import db
from app.models.user import User
from app.schemas.user import LoginRequest, UserCreate, UserOut, UserUpdate
from app.services.auth_service import hash_password, issue_tokens, verify_password
from app.utils.auth_guards import roles_required
from app.utils.errors import error_response

bp = Blueprint("auth", __name__, url_prefix="/api/v1/auth")


@bp.post("/login")
def login():
    try:
        payload = LoginRequest.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )

    user = db.session.query(User).filter(User.email == payload.email.lower()).first()
    if user is None or not user.activo or not verify_password(payload.password, user.password_hash):
        return error_response("credenciales inválidas", 401, "invalid_credentials")

    access, refresh = issue_tokens(user)
    return jsonify(
        {
            "access_token": access,
            "refresh_token": refresh,
            "user": UserOut.model_validate(user).model_dump(mode="json"),
        }
    )


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    identity = get_jwt_identity()
    user = db.session.get(User, int(identity))
    if user is None or not user.activo:
        return error_response("usuario no disponible", 401, "invalid_user")
    claims = {
        "rol": user.rol.value,
        "sucursal_id": user.sucursal_id,
        "email": user.email,
    }
    access = create_access_token(identity=str(user.id), additional_claims=claims)
    return jsonify({"access_token": access})


@bp.get("/me")
@jwt_required()
def me():
    identity = get_jwt_identity()
    user = db.session.get(User, int(identity))
    if user is None:
        return error_response("usuario inexistente", 404, "not_found")
    return jsonify(UserOut.model_validate(user).model_dump(mode="json"))


@bp.post("/register")
@roles_required("admin")
def register():
    try:
        payload = UserCreate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )

    email = payload.email.lower()
    if db.session.query(User).filter(User.email == email).first():
        return error_response("email ya registrado", 409, "email_taken")

    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        nombre=payload.nombre,
        rol=payload.rol,
        sucursal_id=payload.sucursal_id,
        activo=payload.activo,
    )
    db.session.add(user)
    db.session.commit()

    return jsonify(UserOut.model_validate(user).model_dump(mode="json")), 201


@bp.get("/users")
@roles_required("admin")
def list_users():
    rows = (
        db.session.execute(select(User).order_by(User.email)).scalars().all()
    )
    return jsonify([UserOut.model_validate(u).model_dump(mode="json") for u in rows])


@bp.patch("/users/<int:user_id>")
@roles_required("admin")
def update_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return error_response("usuario no encontrado", 404, "not_found")

    try:
        payload = UserUpdate.model_validate(request.get_json(silent=True) or {})
    except ValidationError as err:
        return error_response(
            "validation_error", 422, "validation_error", err.errors(include_url=False)
        )

    data = payload.model_dump(exclude_unset=True)
    if "password" in data:
        pwd = data.pop("password")
        if pwd:
            user.password_hash = hash_password(pwd)
    for k, v in data.items():
        setattr(user, k, v)
    db.session.commit()
    return jsonify(UserOut.model_validate(user).model_dump(mode="json"))


@bp.delete("/users/<int:user_id>")
@roles_required("admin")
def delete_user(user_id: int):
    user = db.session.get(User, user_id)
    if user is None:
        return error_response("usuario no encontrado", 404, "not_found")
    user.activo = False
    db.session.commit()
    return "", 204


# Noop para silenciar unused import de get_jwt (lo usamos implícitamente via decoradores).
_ = get_jwt
