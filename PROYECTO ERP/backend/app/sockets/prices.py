"""Namespace SocketIO /prices — broadcast de cambios de precio en vivo.

Protocolo handshake:
- Cliente conecta con `auth: {token: <jwt>}` (Socket.IO v4) o ?token=<jwt> querystring.
- Se decodifica con flask_jwt_extended.decode_token.
- Si es inválido o expirado, se rechaza (`return False`).
- Si OK, el socket entra al room `all` y — si el usuario tiene sucursal_id — al
  room `sucursal:{id}`.
"""
from __future__ import annotations

import logging
from typing import Any

from flask import request
from flask_jwt_extended import decode_token
from flask_socketio import Namespace, join_room, leave_room

from app.extensions import socketio

logger = logging.getLogger(__name__)


def _extract_token(auth: dict | None) -> str | None:
    """Saca el token JWT del payload auth o de la query string."""
    if isinstance(auth, dict):
        token = auth.get("token")
        if isinstance(token, str) and token:
            return token
    # Fallback: ?token=xxx en la query del handshake
    token = request.args.get("token")
    if isinstance(token, str) and token:
        return token
    # Fallback: header Authorization: Bearer <token>
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        return header[len("Bearer ") :].strip() or None
    return None


class PricesNamespace(Namespace):
    """Namespace /prices con handshake JWT."""

    def on_connect(self, auth: dict | None = None) -> bool:
        token = _extract_token(auth)
        if not token:
            logger.info("socket /prices: conexión rechazada — sin token")
            return False
        try:
            decoded = decode_token(token, allow_expired=False)
        except Exception as exc:  # jwt exceptions, werkzeug, etc.
            logger.info("socket /prices: token inválido — %s", exc)
            return False

        user_id = decoded.get("sub")
        sucursal_id = decoded.get("sucursal_id")
        email = decoded.get("email")
        rol = decoded.get("rol")

        join_room("all")
        if sucursal_id:
            join_room(f"sucursal:{sucursal_id}")

        logger.info(
            "socket /prices: conectado sid=%s user=%s email=%s rol=%s suc=%s",
            request.sid,
            user_id,
            email,
            rol,
            sucursal_id,
        )
        return True

    def on_disconnect(self) -> None:
        logger.info("socket /prices: desconectado sid=%s", request.sid)
        # leave_room es implícito al desconectar, pero lo logueamos explícito.
        try:
            leave_room("all")
        except Exception:
            pass

    def on_ping(self, data: Any) -> None:  # debug helper
        socketio.emit("pong", {"sid": request.sid}, namespace="/prices", to=request.sid)


def register_prices_namespace() -> None:
    socketio.on_namespace(PricesNamespace("/prices"))
