"""Fixture script: inserta movimientos sospechosos en la DB demo para
disparar todos los detectores de alertas en `flask alerts run`.

Uso (desde backend/, con la DB ya seedeada con `flask seed big`):

    .venv/Scripts/python.exe -m tests.fixtures.duplicados

Idempotente: si los movimientos ya existen (por descripción match exacto),
no los re-inserta.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app import create_app
from app.extensions import db
from app.models.proveedor import Proveedor
from app.models.resumen import MovimientoCaja, TipoMovimientoEnum
from app.models.sucursal import Sucursal
from app.models.user import RolEnum, User


MARKER_DESC = "[FIXTURE-DUPLICADOS]"


def _existe_marker() -> bool:
    return (
        db.session.query(MovimientoCaja)
        .filter(MovimientoCaja.descripcion.like(f"{MARKER_DESC}%"))
        .first()
        is not None
    )


def insert_sospechosos() -> dict[str, int]:
    """Inserta movimientos que dispararán cada detector. Retorna dict de conteos."""
    if _existe_marker():
        print("Fixtures ya insertados — skip.")
        return {"insertados": 0}

    suc = db.session.query(Sucursal).first()
    if suc is None:
        raise RuntimeError("No hay sucursales — corré primero `flask seed big`.")

    proveedores = db.session.query(Proveedor).limit(3).all()
    if len(proveedores) < 2:
        raise RuntimeError(
            "No hay suficientes proveedores — corré `flask seed big` primero."
        )

    cajero = (
        db.session.query(User)
        .filter(User.rol == RolEnum.cajero)
        .first()
    )
    user_id = cajero.id if cajero else None

    now = datetime.now(timezone.utc)
    inserted = 0

    # 1) Pago duplicado al mismo proveedor (mismo monto, 2 días de diferencia)
    p0 = proveedores[0]
    for delta in (0, 2):
        db.session.add(
            MovimientoCaja(
                sucursal_id=suc.id,
                caja_numero=1,
                fecha_caja=(now - timedelta(days=delta)).date(),
                fecha=now - timedelta(days=delta),
                tipo=TipoMovimientoEnum.pago_proveedor,
                monto=Decimal("-150000.00"),
                proveedor_id=p0.id,
                descripcion=f"{MARKER_DESC} pago duplicado A",
                user_id=user_id,
            )
        )
        inserted += 1

    # 2) Factura compra repetida (3 pagos exactos al mismo proveedor en 7 días)
    p1 = proveedores[1]
    for delta in (0, 3, 5):
        db.session.add(
            MovimientoCaja(
                sucursal_id=suc.id,
                caja_numero=1,
                fecha_caja=(now - timedelta(days=delta)).date(),
                fecha=now - timedelta(days=delta),
                tipo=TipoMovimientoEnum.pago_proveedor,
                monto=Decimal("-89500.75"),
                proveedor_id=p1.id,
                descripcion=f"{MARKER_DESC} compra repetida B",
                user_id=user_id,
            )
        )
        inserted += 1

    # 3) Ajuste stock sospechoso — manual sin venta correlacionada
    db.session.add(
        MovimientoCaja(
            sucursal_id=suc.id,
            caja_numero=1,
            fecha_caja=now.date(),
            fecha=now,
            tipo=TipoMovimientoEnum.ajuste,
            monto=Decimal("-78000.00"),
            descripcion=f"{MARKER_DESC} ajuste manual stock",
            user_id=user_id,
        )
    )
    inserted += 1

    db.session.commit()
    return {"insertados": inserted}


def main():
    app = create_app()
    with app.app_context():
        result = insert_sospechosos()
        print(f"Insertados: {result['insertados']} movimientos sospechosos.")


if __name__ == "__main__":
    main()
