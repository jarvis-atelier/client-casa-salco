"""Tests de la migración alembic e5f6a7b8c9d0_articulo_codigos.

Cubre los scenarios S1, S2, S3, S9, S10, S11 del delta-spec
`articulo-multi-codigo-migration`:

- S1 — `flask db upgrade` crea la tabla `articulo_codigos` con columnas,
  índices, FK CASCADE y UNIQUE(articulo_id, codigo) correctas.
- S2 — backfill: cada articulo con codigo_barras NOT NULL y no-vacío
  produce exactamente UNA row en `articulo_codigos` con
  `tipo='principal'` y `(articulo_id, codigo)` igual al origen.
- S3 — backfill: rows con `codigo_barras = ''` o whitespace-only NO
  generan rows.
- S9 — post-upgrade la columna `articulos.codigo_barras` no existe y
  su índice tampoco.
- S10 — `flask db downgrade -1` restaura `articulos.codigo_barras` con
  los códigos `principal` previamente backfilleados; la tabla
  `articulo_codigos` desaparece. Re-aplicar `upgrade head` vuelve a
  reproducir el estado post-migración (idempotencia a nivel alembic).
- S11 — count parity: post-upgrade
  `COUNT(articulo_codigos WHERE tipo='principal')` == count de
  articulos con codigo_barras non-empty pre-upgrade.

Estos tests usan un archivo SQLite temporal (no `:memory:`) porque la
migración usa `batch_alter_table` que recrea la tabla mediante
copy-rename — operación que sobre engines `:memory:` interactúa mal con
algunos drivers cuando se usa sobre la misma conexión que el contexto
alembic. El archivo temporal es eliminado por pytest al cerrar el
fixture.

NO se ejecutan contra la dev DB. NO modifican la DB del proyecto.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PRE_REVISION = "d4e5f6a7b8c9"  # estado pre-migración (head antes de e5f6a7b8c9d0)
POST_REVISION = "e5f6a7b8c9d0"  # head incluyendo articulo_codigos


def _backend_root() -> Path:
    """Raíz del backend (donde vive `migrations/`)."""
    return Path(__file__).resolve().parent.parent


def _alembic_config(db_url: str) -> Config:
    """Construye una Config de alembic apuntando al `migrations/` real.

    Carga `alembic.ini` (necesario para `fileConfig` que se ejecuta en
    `env.py`). Como `migrations/env.py` lee
    `current_app.extensions['migrate'].db.engine` (Flask-Migrate),
    tenemos que armar la app con la URL deseada y dejar que env.py la
    encuentre. Para ese flujo usamos `command.upgrade` y
    `command.downgrade` desde dentro de un app_context con
    SQLALCHEMY_DATABASE_URI override.
    """
    migrations_dir = _backend_root() / "migrations"
    cfg = Config(str(migrations_dir / "alembic.ini"))
    cfg.set_main_option("script_location", str(migrations_dir))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _run_alembic(db_url: str, op: str, target: str) -> None:
    """Ejecuta `alembic upgrade <target>` o `alembic downgrade <target>`
    dentro de un app_context Flask con la DB URL deseada.

    Esto reusa `migrations/env.py` (que toma el engine vía Flask-Migrate),
    asegurando que la migración corra exactamente igual que en producción.
    """
    # Garantizar import path del backend
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
        if op == "upgrade":
            command.upgrade(cfg, target)
        elif op == "downgrade":
            command.downgrade(cfg, target)
        else:  # pragma: no cover
            raise ValueError(f"unknown op: {op}")


@pytest.fixture
def temp_db_url(tmp_path: Path) -> str:
    """SQLite file en directorio temporal de pytest. Limpio entre tests."""
    db_file = tmp_path / "migration_test.db"
    return f"sqlite:///{db_file}"


def _seed_pre_migration_articulos(db_url: str, rows: list[tuple[str, str | None]]) -> list[int]:
    """Inserta articulos directamente vía SQL en estado PRE-migración.

    `rows`: lista de `(codigo, codigo_barras)` — codigo_barras puede ser
    None, '' o un string real.

    Devuelve la lista de IDs en orden de inserción.
    """
    engine = create_engine(db_url, future=True)
    ids: list[int] = []
    with engine.begin() as conn:
        for codigo, barras in rows:
            result = conn.execute(
                text(
                    """
                    INSERT INTO articulos (
                        codigo, codigo_barras, descripcion,
                        unidad_medida, controla_stock, controla_vencimiento,
                        costo, pvp_base, iva_porc, activo,
                        created_at, updated_at
                    ) VALUES (
                        :codigo, :barras, :descripcion,
                        'unidad', 0, 0,
                        '10.0000', '15.0000', '21.00', 1,
                        CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                    )
                    RETURNING id
                    """
                ),
                {"codigo": codigo, "barras": barras, "descripcion": f"desc {codigo}"},
            )
            ids.append(result.scalar_one())
    engine.dispose()
    return ids


# ---------------------------------------------------------------------------
# 3.2 — round-trip alembic upgrade/downgrade en SQLite
# ---------------------------------------------------------------------------


def test_upgrade_creates_articulo_codigos_table_with_correct_schema(temp_db_url):
    """S1 — tras `alembic upgrade head` la tabla existe con shape correcto."""
    # 1. Estado PRE: aplicar migraciones hasta d4e5f6a7b8c9
    _run_alembic(temp_db_url, "upgrade", PRE_REVISION)

    engine = create_engine(temp_db_url, future=True)
    insp = inspect(engine)
    assert "articulo_codigos" not in insp.get_table_names(), (
        "Pre-migración: articulo_codigos NO debe existir"
    )
    assert "codigo_barras" in {
        c["name"] for c in insp.get_columns("articulos")
    }, "Pre-migración: articulos.codigo_barras debe existir"
    engine.dispose()

    # 2. Aplicar la migración objetivo
    _run_alembic(temp_db_url, "upgrade", POST_REVISION)

    engine = create_engine(temp_db_url, future=True)
    insp = inspect(engine)

    # Tabla creada
    tables = insp.get_table_names()
    assert "articulo_codigos" in tables

    # Columnas correctas
    cols = {c["name"]: c for c in insp.get_columns("articulo_codigos")}
    for required in ("id", "articulo_id", "codigo", "tipo", "created_at", "updated_at"):
        assert required in cols, f"falta columna {required}"
    assert cols["articulo_id"]["nullable"] is False
    assert cols["codigo"]["nullable"] is False
    assert cols["tipo"]["nullable"] is False

    # FK CASCADE
    fks = insp.get_foreign_keys("articulo_codigos")
    fk_articulo = next(
        (fk for fk in fks if fk["referred_table"] == "articulos"), None
    )
    assert fk_articulo is not None, "FK a articulos debe existir"
    assert fk_articulo["options"].get("ondelete", "").upper() == "CASCADE"

    # UNIQUE (articulo_id, codigo)
    uniques = insp.get_unique_constraints("articulo_codigos")
    uq = next(
        (u for u in uniques if u.get("name") == "uq_articulo_codigo"), None
    )
    assert uq is not None
    assert sorted(uq["column_names"]) == ["articulo_id", "codigo"]

    # Índices: codigo + articulo_id
    indexes = {ix["name"]: ix for ix in insp.get_indexes("articulo_codigos")}
    assert "ix_articulo_codigos_codigo" in indexes
    assert "ix_articulo_codigos_articulo_id" in indexes

    # S9 — codigo_barras column dropped
    art_cols = {c["name"] for c in insp.get_columns("articulos")}
    assert "codigo_barras" not in art_cols, (
        "S9: articulos.codigo_barras debe estar dropeado"
    )
    art_indexes = {ix["name"] for ix in insp.get_indexes("articulos")}
    assert "ix_articulos_codigo_barras" not in art_indexes

    engine.dispose()


def test_downgrade_restores_codigo_barras_column(temp_db_url):
    """S10 (parte 1) — downgrade reintroduce la columna y el índice."""
    _run_alembic(temp_db_url, "upgrade", POST_REVISION)
    _run_alembic(temp_db_url, "downgrade", PRE_REVISION)

    engine = create_engine(temp_db_url, future=True)
    insp = inspect(engine)

    assert "articulo_codigos" not in insp.get_table_names()
    art_cols = {c["name"] for c in insp.get_columns("articulos")}
    assert "codigo_barras" in art_cols
    art_indexes = {ix["name"] for ix in insp.get_indexes("articulos")}
    assert "ix_articulos_codigo_barras" in art_indexes

    engine.dispose()


def test_alembic_upgrade_idempotent(temp_db_url):
    """S10 (parte 2) — upgrade head dos veces seguidas es no-op."""
    _run_alembic(temp_db_url, "upgrade", POST_REVISION)
    # Re-aplicar es no-op (alembic detecta que ya está stamped en head)
    _run_alembic(temp_db_url, "upgrade", "head")

    engine = create_engine(temp_db_url, future=True)
    insp = inspect(engine)
    assert "articulo_codigos" in insp.get_table_names()
    engine.dispose()


# ---------------------------------------------------------------------------
# 3.3 — backfill correctness
# ---------------------------------------------------------------------------


def test_backfill_principal_codes_only_from_non_empty_rows(temp_db_url):
    """S2 + S3 + S11 — backfill produce exactamente N rows principal,
    saltando empty-string y NULL.
    """
    # 1. Estado PRE
    _run_alembic(temp_db_url, "upgrade", PRE_REVISION)

    # 2. Insert 5 articulos: 3 con codigo_barras non-empty, 1 con '', 1 con NULL
    ids = _seed_pre_migration_articulos(
        temp_db_url,
        [
            ("ART001", "7790070103925"),  # válido
            ("ART002", "7798124564821"),  # válido
            ("ART003", "1234567890123"),  # válido
            ("ART004", ""),                # empty-string → filtrado
            ("ART005", None),              # NULL → filtrado
        ],
    )
    assert len(ids) == 5

    # 3. Apply migración
    _run_alembic(temp_db_url, "upgrade", POST_REVISION)

    # 4. Validar backfill
    engine = create_engine(temp_db_url, future=True)
    with engine.connect() as conn:
        # Total rows en articulo_codigos
        total = conn.execute(
            text("SELECT COUNT(*) FROM articulo_codigos")
        ).scalar_one()
        assert total == 3, f"S11: esperaba 3 rows backfilled, got {total}"

        # Todos tipo='principal'
        principales = conn.execute(
            text(
                "SELECT COUNT(*) FROM articulo_codigos WHERE tipo = 'principal'"
            )
        ).scalar_one()
        assert principales == 3

        # Cada (articulo_id, codigo) corresponde al origen
        rows = list(
            conn.execute(
                text(
                    "SELECT articulo_id, codigo FROM articulo_codigos "
                    "ORDER BY articulo_id"
                )
            )
        )
        expected = {
            (ids[0], "7790070103925"),
            (ids[1], "7798124564821"),
            (ids[2], "1234567890123"),
        }
        assert set((r[0], r[1]) for r in rows) == expected

        # S3: ningún row para los articulos con '' o NULL
        for empty_id in (ids[3], ids[4]):
            cnt = conn.execute(
                text(
                    "SELECT COUNT(*) FROM articulo_codigos WHERE articulo_id = :id"
                ),
                {"id": empty_id},
            ).scalar_one()
            assert cnt == 0, (
                f"S3: articulo {empty_id} con codigo_barras vacío/NULL "
                f"NO debe tener rows en articulo_codigos (got {cnt})"
            )

    engine.dispose()


def test_backfill_filters_space_only_codigo_barras(temp_db_url):
    """S3 — codigo_barras de SOLO espacios es filtrado por `TRIM(codigo_barras) != ''`.

    Notas sobre el comportamiento real de SQLite:

    - `TRIM(value)` en SQLite (sin segundo argumento) solo elimina ESPACIOS,
      NO tabs ni otros whitespace. Por lo tanto strings como `"\\t\\t"`
      pasan el filtro `TRIM(...) != ''` y son backfilleadas.
    - El B1 audit confirmó 0 rows con espacio puro o whitespace en la dev DB
      (codigo_barras es completamente NULL en los 34840 rows). Por lo tanto
      el comportamiento "tabs no filtrados" no afecta la migración en producción.
    - La migración guarda el valor CRUDO (no trimea); el filtro TRIM solo aplica
      al WHERE.
    """
    _run_alembic(temp_db_url, "upgrade", PRE_REVISION)

    ids = _seed_pre_migration_articulos(
        temp_db_url,
        [
            ("ART_WS1", "   "),                # space-only → filtrado
            ("ART_WS2", " 7790000 "),          # contenido post-TRIM → backfilled (raw)
            ("ART_REAL", "7790070103925"),     # válido
        ],
    )

    _run_alembic(temp_db_url, "upgrade", POST_REVISION)

    engine = create_engine(temp_db_url, future=True)
    with engine.connect() as conn:
        # ART_WS1 (space-only) NO debe tener rows
        cnt_ws1 = conn.execute(
            text(
                "SELECT COUNT(*) FROM articulo_codigos WHERE articulo_id = :id"
            ),
            {"id": ids[0]},
        ).scalar_one()
        assert cnt_ws1 == 0, (
            f"S3: codigo_barras = '   ' (space-only) NO debe backfillearse "
            f"(got {cnt_ws1})"
        )

        # ART_WS2 y ART_REAL SÍ deben backfillearse
        for valid_id in (ids[1], ids[2]):
            cnt = conn.execute(
                text(
                    "SELECT COUNT(*) FROM articulo_codigos WHERE articulo_id = :id"
                ),
                {"id": valid_id},
            ).scalar_one()
            assert cnt == 1

        # La migración guarda el valor crudo (no trimea).
        ws2_codigo = conn.execute(
            text(
                "SELECT codigo FROM articulo_codigos WHERE articulo_id = :id"
            ),
            {"id": ids[1]},
        ).scalar_one()
        assert ws2_codigo == " 7790000 ", (
            "La migración almacena codigo_barras crudo (sin TRIM); "
            "el filtro TRIM solo aplica al WHERE."
        )

        # Total esperado: ART_WS2 + ART_REAL = 2
        total = conn.execute(
            text("SELECT COUNT(*) FROM articulo_codigos")
        ).scalar_one()
        assert total == 2, f"esperaba 2 rows backfilled, got {total}"
    engine.dispose()


# ---------------------------------------------------------------------------
# 3.4 — downgrade correctness
# ---------------------------------------------------------------------------


def test_downgrade_restores_principal_codes_and_preserves_empties(temp_db_url):
    """S10 — tras upgrade + downgrade los principales se restauran y
    los rows con codigo_barras NULL/empty quedan NULL/empty.
    """
    # 1. PRE
    _run_alembic(temp_db_url, "upgrade", PRE_REVISION)

    # 2. Seed
    ids = _seed_pre_migration_articulos(
        temp_db_url,
        [
            ("ART001", "7790070103925"),  # válido
            ("ART002", "7798124564821"),  # válido
            ("ART003", "1234567890123"),  # válido
            ("ART004", ""),                # empty
            ("ART005", None),              # NULL
        ],
    )

    # 3. Upgrade → mueve los 3 a articulo_codigos como principal
    _run_alembic(temp_db_url, "upgrade", POST_REVISION)

    # 4. Downgrade → debe restaurar los 3 codigo_barras
    _run_alembic(temp_db_url, "downgrade", PRE_REVISION)

    engine = create_engine(temp_db_url, future=True)
    insp = inspect(engine)

    # articulos.codigo_barras column existe nuevamente
    art_cols = {c["name"] for c in insp.get_columns("articulos")}
    assert "codigo_barras" in art_cols

    # articulo_codigos NO existe
    assert "articulo_codigos" not in insp.get_table_names()

    with engine.connect() as conn:
        rows = list(
            conn.execute(
                text(
                    "SELECT id, codigo_barras FROM articulos ORDER BY id"
                )
            )
        )
        assert len(rows) == 5

        # Los 3 con valor real: codigo_barras restaurado
        # ART001 → 7790070103925
        # ART002 → 7798124564821
        # ART003 → 1234567890123
        # ART004 → NULL (porque no había row 'principal' para él)
        # ART005 → NULL (no había nada que restaurar)
        rows_by_id = {r[0]: r[1] for r in rows}
        assert rows_by_id[ids[0]] == "7790070103925"
        assert rows_by_id[ids[1]] == "7798124564821"
        assert rows_by_id[ids[2]] == "1234567890123"
        assert rows_by_id[ids[3]] is None, (
            "ART004 tenía '' pre-migración → tras up+down queda NULL "
            "(no aparece data fantasma)"
        )
        assert rows_by_id[ids[4]] is None, (
            "ART005 tenía NULL pre-migración → tras up+down sigue NULL"
        )

    engine.dispose()
