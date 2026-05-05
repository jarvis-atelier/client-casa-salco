"""Tests de la migración alembic f6a7b8c9d0e1_articulo_proveedor_cantidad.

Cubre el scenario S1 del delta-spec `xls-empaquetados-y-presentaciones`:

- S1 — `alembic upgrade head` agrega `articulo_proveedores.cantidad_por_pack`
  como `Numeric(10, 3)` NOT NULL con `server_default=1`. Filas pre-existentes
  reciben `cantidad_por_pack = 1` por el server-default.
- S1 (downgrade) — `alembic downgrade -1` elimina la columna sin tocar las
  demás de la tabla.

Mirror del patrón usado por `test_articulo_codigos_migration.py` (Change A).
SQLite file en directorio temporal de pytest (no `:memory:` porque
`batch_alter_table` recrea la tabla mediante copy-rename).

NO se ejecuta contra la dev DB. NO modifica la DB del proyecto.
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PRE_REVISION = "e5f6a7b8c9d0"  # head Change A — pre cantidad_por_pack
POST_REVISION = "f6a7b8c9d0e1"  # head Change B — incluye cantidad_por_pack


def _backend_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _alembic_config(db_url: str) -> Config:
    migrations_dir = _backend_root() / "migrations"
    cfg = Config(str(migrations_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _run_alembic(db_url: str, op_name: str, target: str) -> None:
    backend_root = _backend_root()
    if str(backend_root) not in sys.path:
        sys.path.insert(0, str(backend_root))

    from app import create_app  # type: ignore[import-not-found]

    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": db_url,
        }
    )
    with app.app_context():
        cfg = _alembic_config(db_url)
        if op_name == "upgrade":
            command.upgrade(cfg, target)
        elif op_name == "downgrade":
            command.downgrade(cfg, target)
        else:  # pragma: no cover
            raise ValueError(f"unknown op: {op_name}")


@pytest.fixture
def temp_db_url(tmp_path: Path) -> str:
    db_file = tmp_path / "cantidad_migration_test.db"
    return f"sqlite:///{db_file}"


def _seed_articulo_proveedor(
    db_url: str,
    rows: list[tuple[str, str, str]],
) -> tuple[list[int], list[int]]:
    """Inserta articulos + proveedores + articulo_proveedores en estado PRE.

    `rows`: lista de `(articulo_codigo, proveedor_codigo, proveedor_razon)`.
    Retorna `(articulo_ids, proveedor_ids)`.
    """
    engine = create_engine(db_url, future=True)
    art_ids: list[int] = []
    prov_ids: list[int] = []
    with engine.begin() as conn:
        for art_codigo, prov_codigo, razon in rows:
            art_id = conn.execute(
                text(
                    """
                    INSERT INTO articulos (
                        codigo, descripcion,
                        unidad_medida, controla_stock, controla_vencimiento,
                        costo, pvp_base, iva_porc, activo,
                        created_at, updated_at
                    ) VALUES (
                        :codigo, :descripcion,
                        'unidad', 0, 0,
                        '10.0000', '15.0000', '21.00', 1,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    RETURNING id
                    """
                ),
                {"codigo": art_codigo, "descripcion": f"desc {art_codigo}"},
            ).scalar_one()
            art_ids.append(art_id)

            prov_id = conn.execute(
                text(
                    """
                    INSERT INTO proveedores (
                        codigo, razon_social, activo,
                        created_at, updated_at
                    ) VALUES (
                        :codigo, :razon, 1,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    RETURNING id
                    """
                ),
                {"codigo": prov_codigo, "razon": razon},
            ).scalar_one()
            prov_ids.append(prov_id)

            conn.execute(
                text(
                    """
                    INSERT INTO articulo_proveedores (
                        articulo_id, proveedor_id,
                        codigo_proveedor, costo_proveedor,
                        created_at, updated_at
                    ) VALUES (
                        :art_id, :prov_id,
                        NULL, '10.0000',
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    """
                ),
                {"art_id": art_id, "prov_id": prov_id},
            )
    engine.dispose()
    return art_ids, prov_ids


# ---------------------------------------------------------------------------
# 3.2 — round-trip alembic upgrade/downgrade en SQLite
# ---------------------------------------------------------------------------


def test_upgrade_adds_cantidad_por_pack_column(temp_db_url):
    """S1 — tras `alembic upgrade head` la columna existe con tipo Numeric(10,3) NOT NULL."""
    _run_alembic(temp_db_url, "upgrade", PRE_REVISION)

    engine = create_engine(temp_db_url, future=True)
    insp = inspect(engine)
    pre_cols = {c["name"] for c in insp.get_columns("articulo_proveedores")}
    assert "cantidad_por_pack" not in pre_cols, (
        "Pre-migración: cantidad_por_pack NO debe existir"
    )
    engine.dispose()

    _run_alembic(temp_db_url, "upgrade", POST_REVISION)

    engine = create_engine(temp_db_url, future=True)
    insp = inspect(engine)
    cols = {c["name"]: c for c in insp.get_columns("articulo_proveedores")}
    assert "cantidad_por_pack" in cols, "S1: columna creada"
    col = cols["cantidad_por_pack"]
    assert col["nullable"] is False, "S1: NOT NULL"
    # SQLAlchemy reflection devuelve NUMERIC(10, 3) — chequeo robusto sobre repr
    type_repr = str(col["type"]).upper()
    assert "NUMERIC" in type_repr, f"S1: esperaba NUMERIC, got {type_repr!r}"
    # precision/scale via type object cuando esté disponible
    if hasattr(col["type"], "precision"):
        assert col["type"].precision == 10
        assert col["type"].scale == 3
    engine.dispose()


def test_upgrade_existing_rows_default_to_one(temp_db_url):
    """S1 — filas pre-existentes reciben cantidad_por_pack=1 por server_default."""
    # 1. Aplicar hasta PRE-migración
    _run_alembic(temp_db_url, "upgrade", PRE_REVISION)

    # 2. Sembrar 3 articulos + 3 proveedores + 3 articulo_proveedores
    art_ids, prov_ids = _seed_articulo_proveedor(
        temp_db_url,
        [
            ("ART001", "PROV001", "Proveedor A"),
            ("ART002", "PROV002", "Proveedor B"),
            ("ART003", "PROV003", "Proveedor C"),
        ],
    )
    assert len(art_ids) == 3

    # 3. Aplicar la migración
    _run_alembic(temp_db_url, "upgrade", POST_REVISION)

    # 4. Validar que las 3 filas tienen cantidad_por_pack=1
    engine = create_engine(temp_db_url, future=True)
    with engine.connect() as conn:
        total = conn.execute(
            text("SELECT COUNT(*) FROM articulo_proveedores")
        ).scalar_one()
        assert total == 3

        rows = list(
            conn.execute(
                text(
                    "SELECT articulo_id, cantidad_por_pack "
                    "FROM articulo_proveedores ORDER BY articulo_id"
                )
            )
        )
        for art_id, cantidad in rows:
            # SQLite returns Decimal-compatible value via Numeric type
            assert Decimal(str(cantidad)) == Decimal("1"), (
                f"articulo {art_id}: cantidad_por_pack debería ser 1 "
                f"(server_default), got {cantidad!r}"
            )
    engine.dispose()


def test_downgrade_removes_cantidad_por_pack(temp_db_url):
    """S1 — `alembic downgrade -1` elimina la columna sin tocar las demás."""
    _run_alembic(temp_db_url, "upgrade", POST_REVISION)
    _run_alembic(temp_db_url, "downgrade", PRE_REVISION)

    engine = create_engine(temp_db_url, future=True)
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("articulo_proveedores")}
    assert "cantidad_por_pack" not in cols, "S1: columna dropeada en downgrade"
    # Las demás columnas de articulo_proveedores siguen presentes
    for required in (
        "id",
        "articulo_id",
        "proveedor_id",
        "codigo_proveedor",
        "costo_proveedor",
        "ultimo_ingreso",
        "created_at",
        "updated_at",
    ):
        assert required in cols, f"S1: columna {required} no debe perderse"
    engine.dispose()


def test_alembic_upgrade_idempotent(temp_db_url):
    """`alembic upgrade head` aplicado dos veces es no-op."""
    _run_alembic(temp_db_url, "upgrade", POST_REVISION)
    _run_alembic(temp_db_url, "upgrade", "head")

    engine = create_engine(temp_db_url, future=True)
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("articulo_proveedores")}
    assert "cantidad_por_pack" in cols
    engine.dispose()
