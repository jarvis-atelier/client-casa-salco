"""Sync de precios multi-sucursal + broadcast Socket.IO.

`broadcast_price_update` emite un evento `price:updated` por cada cambio (uno
por par articulo+sucursal) al room `all` del namespace `/prices`.

Payload shape (v1):
{
  "articulo": {"id": N, "codigo": "A001", "descripcion": "..."},
  "sucursal": {"id": N, "codigo": "SUC01", "nombre": "Centro"},
  "precio_anterior": "450.0000" | null,
  "precio_nuevo": "500.0000",
  "motivo": "ajuste semanal" | null,
  "cambiado_por": {"id": N, "email": "x", "nombre": "y"} | null,
  "timestamp": "2026-04-24T15:42:25.123456+00:00"
}
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, select

from app.extensions import db, socketio
from app.models.articulo import Articulo
from app.models.precio import PrecioHistorico, PrecioSucursal
from app.models.sucursal import Sucursal
from app.models.user import User


def _close_active_price(articulo_id: int, sucursal_id: int) -> Decimal | None:
    """Marca inactivos los PrecioSucursal vigentes y devuelve el último precio."""
    previos = (
        db.session.query(PrecioSucursal)
        .filter(
            and_(
                PrecioSucursal.articulo_id == articulo_id,
                PrecioSucursal.sucursal_id == sucursal_id,
                PrecioSucursal.activo.is_(True),
            )
        )
        .all()
    )
    ultimo: Decimal | None = None
    now = datetime.now(UTC)
    for p in previos:
        ultimo = p.precio
        p.activo = False
        p.vigente_hasta = now
    return ultimo


def sucursales_activas_ids() -> list[int]:
    """IDs de sucursales activas no-soft-deleted, ordenados."""
    stmt = select(Sucursal.id).where(
        Sucursal.activa.is_(True), Sucursal.deleted_at.is_(None)
    ).order_by(Sucursal.id)
    return list(db.session.execute(stmt).scalars().all())


def actualizar_precios(
    articulo_id: int,
    updates: list[tuple[int, Decimal]],
    user_id: int | None,
    motivo: str | None,
) -> list[dict[str, Any]]:
    """Actualiza precios en N sucursales para un artículo.

    - Cierra el PrecioSucursal activo anterior (vigente_hasta=now, activo=False).
    - Inserta uno nuevo por cada sucursal.
    - Escribe registro en PrecioHistorico.
    - Commit transaccional.
    - Emite un `price:updated` por cada cambio al room `all` de /prices.

    Devuelve una lista de dicts con `sucursal_id`, `precio_anterior`, `precio_nuevo`.
    """
    articulo = db.session.get(Articulo, articulo_id)
    if articulo is None or articulo.deleted_at is not None:
        raise ValueError(f"Articulo {articulo_id} inexistente")

    cambiado_por: User | None = (
        db.session.get(User, user_id) if user_id is not None else None
    )

    # Validar sucursales antes de tocar nada — si alguna no existe, abortamos.
    sucursal_ids = [s for s, _ in updates]
    sucursales_map: dict[int, Sucursal] = {
        s.id: s
        for s in db.session.query(Sucursal)
        .filter(Sucursal.id.in_(sucursal_ids), Sucursal.deleted_at.is_(None))
        .all()
    }
    faltantes = [sid for sid in sucursal_ids if sid not in sucursales_map]
    if faltantes:
        raise ValueError(
            f"Sucursal(es) inexistente(s): {', '.join(str(x) for x in faltantes)}"
        )

    resumen: list[dict[str, Any]] = []
    nuevos_rows: list[PrecioSucursal] = []

    for sucursal_id, precio in updates:
        anterior = _close_active_price(articulo_id, sucursal_id)

        nuevo = PrecioSucursal(
            articulo_id=articulo_id,
            sucursal_id=sucursal_id,
            precio=precio,
            activo=True,
            updated_by_user_id=user_id,
        )
        db.session.add(nuevo)
        nuevos_rows.append(nuevo)

        db.session.add(
            PrecioHistorico(
                articulo_id=articulo_id,
                sucursal_id=sucursal_id,
                precio_anterior=anterior,
                precio_nuevo=precio,
                cambiado_por_user_id=user_id,
                motivo=motivo,
            )
        )
        resumen.append(
            {
                "sucursal_id": sucursal_id,
                "precio_anterior": str(anterior) if anterior is not None else None,
                "precio_nuevo": str(precio),
            }
        )

    db.session.commit()

    # Broadcast — después del commit, para no emitir si la transacción falla.
    timestamp = datetime.now(UTC).isoformat()
    for item, _row in zip(resumen, nuevos_rows, strict=True):
        sucursal = sucursales_map[item["sucursal_id"]]
        broadcast_price_update(
            {
                "articulo": {
                    "id": articulo.id,
                    "codigo": articulo.codigo,
                    "descripcion": articulo.descripcion,
                },
                "sucursal": {
                    "id": sucursal.id,
                    "codigo": sucursal.codigo,
                    "nombre": sucursal.nombre,
                },
                "precio_anterior": item["precio_anterior"],
                "precio_nuevo": item["precio_nuevo"],
                "motivo": motivo,
                "cambiado_por": (
                    {
                        "id": cambiado_por.id,
                        "email": cambiado_por.email,
                        "nombre": cambiado_por.nombre,
                    }
                    if cambiado_por is not None
                    else None
                ),
                "timestamp": timestamp,
            }
        )

    return resumen


def broadcast_price_update(payload: dict[str, Any]) -> None:
    """Emite `price:updated` al room `all` del namespace `/prices`.

    Nunca bloquea el flujo — si SocketIO no está listo (tests), se ignora.
    """
    try:
        socketio.emit(
            "price:updated",
            payload,
            namespace="/prices",
            to="all",
        )
    except Exception:  # pragma: no cover — defensivo
        pass
