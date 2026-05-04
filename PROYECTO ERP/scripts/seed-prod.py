"""Seed minimo para Postgres de produccion.

Crea SOLO lo indispensable para arrancar:
    - 1 usuario admin (con password hasheada)
    - 1 sucursal default
    - Configuracion de comercio basica

NO crea data demo (articulos, clientes ficticios, etc) - eso queda para dev/staging.

Uso:
    DATABASE_URL=postgresql+psycopg://... \\
    ADMIN_EMAIL=admin@jarvis.com \\
    ADMIN_PASSWORD=cambiar-ya-mismo \\
    python scripts/seed-prod.py

Idempotente: si el admin ya existe, no falla, solo skip.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Permitimos ejecutar el script desde la raiz del repo
ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

try:
    import bcrypt  # noqa: E402
    from sqlalchemy import create_engine, text  # noqa: E402
    from sqlalchemy.orm import Session  # noqa: E402
except ImportError as e:
    print(f"ERROR: faltan deps. Instalar el backend primero: pip install -e backend/[exports]")
    print(f"  {e}")
    sys.exit(1)


def seed() -> None:
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DATABASE_URL no esta seteada")
        sys.exit(1)

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@jarvis.com")
    admin_password = os.environ.get("ADMIN_PASSWORD")
    if not admin_password:
        print("ERROR: ADMIN_PASSWORD no esta seteada (usa una contrasena fuerte)")
        sys.exit(1)
    if len(admin_password) < 12:
        print("ERROR: ADMIN_PASSWORD debe tener al menos 12 caracteres")
        sys.exit(1)

    engine = create_engine(db_url)

    with Session(engine) as s:
        # 1. Usuario admin
        existing = s.execute(
            text("SELECT id FROM users WHERE email = :e"), {"e": admin_email}
        ).first()
        if existing:
            print(f"  admin {admin_email} ya existe (id={existing[0]}), skip")
        else:
            hashed = bcrypt.hashpw(
                admin_password.encode("utf-8"), bcrypt.gensalt()
            ).decode("utf-8")
            s.execute(
                text(
                    """
                    INSERT INTO users (email, password_hash, role, activo)
                    VALUES (:e, :p, 'admin', true)
                    """
                ),
                {"e": admin_email, "p": hashed},
            )
            print(f"  admin {admin_email} creado")

        # 2. Sucursal default
        existing = s.execute(
            text("SELECT id FROM sucursales WHERE codigo = 'CENTRAL'")
        ).first()
        if existing:
            print(f"  sucursal CENTRAL ya existe (id={existing[0]}), skip")
        else:
            s.execute(
                text(
                    """
                    INSERT INTO sucursales (codigo, nombre, activo)
                    VALUES ('CENTRAL', 'Casa Central', true)
                    """
                )
            )
            print("  sucursal CENTRAL creada")

        # 3. Comercio config (solo si no existe)
        existing = s.execute(text("SELECT id FROM comercio_config LIMIT 1")).first()
        if existing:
            print("  comercio_config ya existe, skip")
        else:
            s.execute(
                text(
                    """
                    INSERT INTO comercio_config (razon_social, cuit, condicion_iva)
                    VALUES ('Mi Comercio', '20000000001', 'RI')
                    """
                )
            )
            print("  comercio_config inicial creado (editar via UI despues)")

        s.commit()

    print("\nSeed completado. Login con:")
    print(f"  email:    {admin_email}")
    print("  password: <la que pasaste por env>")
    print("\nIMPORTANTE: cambiar password admin desde la UI cuanto antes.")


if __name__ == "__main__":
    seed()
