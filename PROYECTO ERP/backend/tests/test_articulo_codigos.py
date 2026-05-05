"""Tests del modelo ArticuloCodigo (tabla 1:N de códigos por artículo).

Cubre los scenarios del delta-spec `articulo-multi-codigo-migration`:

- S1 — schema del modelo (FK + UNIQUE + índice + ondelete CASCADE).
- S7 — el enum `TipoCodigoArticuloEnum` rechaza valores inválidos.
- S8 — UNIQUE `(articulo_id, codigo)` per-pair (mismo código en distintos
  artículos OK; mismo par dos veces falla).
- CASCADE — borrar `Articulo` borra sus `ArticuloCodigo`.
- Backref / relationship — `articulo.codigos` y `codigo.articulo`.

Estos tests usan los fixtures `app`, `db` de `conftest.py` (SQLite
:memory: con `db.create_all()` cargando el metadata completo, incluido
`articulo_codigos`).
"""
from __future__ import annotations

from decimal import Decimal

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.models.articulo import Articulo
from app.models.articulo_codigo import ArticuloCodigo, TipoCodigoArticuloEnum


def _make_articulo(db, codigo: str = "ART001", descripcion: str = "Test") -> Articulo:
    art = Articulo(
        codigo=codigo,
        descripcion=descripcion,
        unidad_medida="unidad",
        controla_stock=True,
        controla_vencimiento=False,
        costo=Decimal("10.00"),
        pvp_base=Decimal("15.00"),
        iva_porc=Decimal("21"),
        activo=True,
    )
    db.session.add(art)
    db.session.commit()
    return art


# ---------------------------------------------------------------------------
# S1 — schema
# ---------------------------------------------------------------------------


def test_table_schema_articulo_codigos_exists(db):
    """S1 — la tabla `articulo_codigos` existe con las columnas esperadas."""
    insp = inspect(db.engine)
    assert "articulo_codigos" in insp.get_table_names()

    cols = {c["name"]: c for c in insp.get_columns("articulo_codigos")}
    for name in ("id", "articulo_id", "codigo", "tipo", "created_at", "updated_at"):
        assert name in cols, f"falta columna {name}"
    assert cols["articulo_id"]["nullable"] is False
    assert cols["codigo"]["nullable"] is False
    assert cols["tipo"]["nullable"] is False


def test_table_schema_fk_cascade(db):
    """S1 — FK `articulo_id` -> articulos.id ON DELETE CASCADE."""
    insp = inspect(db.engine)
    fks = insp.get_foreign_keys("articulo_codigos")
    fk = next((f for f in fks if f["referred_table"] == "articulos"), None)
    assert fk is not None
    assert fk["options"].get("ondelete", "").upper() == "CASCADE"


def test_table_schema_unique_constraint(db):
    """S1 — UNIQUE `(articulo_id, codigo)` named `uq_articulo_codigo`."""
    insp = inspect(db.engine)
    uniques = insp.get_unique_constraints("articulo_codigos")
    uq = next((u for u in uniques if u.get("name") == "uq_articulo_codigo"), None)
    assert uq is not None
    assert sorted(uq["column_names"]) == ["articulo_id", "codigo"]


def test_table_schema_indexes(db):
    """S1 — índices sobre `articulo_id` y `codigo` (POS scan hot path)."""
    insp = inspect(db.engine)
    index_names = {ix["name"] for ix in insp.get_indexes("articulo_codigos")}
    assert "ix_articulo_codigos_articulo_id" in index_names
    assert "ix_articulo_codigos_codigo" in index_names


# ---------------------------------------------------------------------------
# S7 — tipo enum
# ---------------------------------------------------------------------------


def test_tipo_enum_accepts_all_four_values(db):
    """S7 — los 4 valores del enum son aceptados."""
    art = _make_articulo(db, codigo="ART_ENUM")
    for idx, tipo in enumerate(
        (
            TipoCodigoArticuloEnum.principal,
            TipoCodigoArticuloEnum.alterno,
            TipoCodigoArticuloEnum.empaquetado,
            TipoCodigoArticuloEnum.interno,
        )
    ):
        c = ArticuloCodigo(articulo_id=art.id, codigo=f"COD-{idx}", tipo=tipo)
        db.session.add(c)
    db.session.commit()
    assert db.session.query(ArticuloCodigo).count() == 4


def test_tipo_enum_rejects_unknown_value_on_read(db):
    """S7 — un valor de `tipo` inválido es rechazado por SQLAlchemy.

    Notas sobre la enforcement asimétrica SQLite vs Postgres:

    - **Postgres**: la columna `tipo` usa el enum nativo
      `tipo_codigo_articulo_enum`; cualquier INSERT con valor fuera de los
      4 permitidos falla a nivel DB con `InvalidTextRepresentation`.
    - **SQLite**: no soporta enums nativos. SQLAlchemy declara la columna
      como `VARCHAR(11)` y NO añade un CHECK constraint (default
      `create_constraint=False` en `Enum`). El INSERT crudo de un valor
      arbitrario PASA en la DB.
    - La enforcement se aplica al **leer**: SQLAlchemy intenta coercionar
      el string a `TipoCodigoArticuloEnum` y levanta `LookupError`.

    Este test usa un INSERT raw (que omite el adapter ORM) y valida que
    al leer la fila vuelva a rechazarla — esto cubre S7 en los dos
    motores. En Postgres falla al INSERT (más temprano). En SQLite falla
    al SELECT.
    """
    art = _make_articulo(db, codigo="ART_BAD")
    # INSERT raw con valor inválido — bypassea el ORM.
    db.session.execute(
        text(
            "INSERT INTO articulo_codigos "
            "(articulo_id, codigo, tipo, created_at, updated_at) "
            "VALUES (:aid, :c, :tipo, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
        ),
        {"aid": art.id, "c": "BAD-X", "tipo": "foo"},
    )
    db.session.commit()
    db.session.expire_all()

    # Al leer, SQLAlchemy debe coercionar y levantar.
    with pytest.raises(LookupError):
        db.session.query(ArticuloCodigo).filter_by(articulo_id=art.id).all()
    db.session.rollback()


# ---------------------------------------------------------------------------
# S8 — UNIQUE (articulo_id, codigo)
# ---------------------------------------------------------------------------


def test_unique_pair_articulo_codigo_blocks_duplicate(db):
    """S8 — el mismo `(articulo_id, codigo)` dos veces falla."""
    art = _make_articulo(db, codigo="ART_UQ")
    db.session.add(
        ArticuloCodigo(
            articulo_id=art.id, codigo="DUP123", tipo=TipoCodigoArticuloEnum.principal
        )
    )
    db.session.commit()
    db.session.add(
        ArticuloCodigo(
            articulo_id=art.id, codigo="DUP123", tipo=TipoCodigoArticuloEnum.alterno
        )
    )
    with pytest.raises(IntegrityError):
        db.session.commit()
    db.session.rollback()


def test_same_codigo_on_different_articulos_is_allowed(db):
    """S8 — el mismo `codigo` en `articulos` distintos SÍ se permite."""
    art_a = _make_articulo(db, codigo="ART_GLOBAL_A")
    art_b = _make_articulo(db, codigo="ART_GLOBAL_B")
    db.session.add(
        ArticuloCodigo(
            articulo_id=art_a.id,
            codigo="SHARED999",
            tipo=TipoCodigoArticuloEnum.principal,
        )
    )
    db.session.add(
        ArticuloCodigo(
            articulo_id=art_b.id,
            codigo="SHARED999",
            tipo=TipoCodigoArticuloEnum.principal,
        )
    )
    db.session.commit()
    rows = (
        db.session.query(ArticuloCodigo)
        .filter(ArticuloCodigo.codigo == "SHARED999")
        .all()
    )
    assert len(rows) == 2
    assert {r.articulo_id for r in rows} == {art_a.id, art_b.id}


# ---------------------------------------------------------------------------
# CASCADE delete
# ---------------------------------------------------------------------------


def test_delete_articulo_cascades_to_codigos(db):
    """Borrar el Articulo dueño borra todos sus ArticuloCodigo (FK CASCADE).

    Para SQLite hace falta `PRAGMA foreign_keys=ON` por conexión; nos
    apoyamos en el cascade ORM (`cascade="all, delete-orphan"` en
    `Articulo.codigos`) que funciona transversalmente en los engines de
    test (in-memory).
    """
    art = _make_articulo(db, codigo="ART_CASCADE")
    art.codigos.append(
        ArticuloCodigo(codigo="C1", tipo=TipoCodigoArticuloEnum.principal)
    )
    art.codigos.append(
        ArticuloCodigo(codigo="C2", tipo=TipoCodigoArticuloEnum.alterno)
    )
    db.session.commit()
    art_id = art.id
    assert db.session.query(ArticuloCodigo).filter_by(articulo_id=art_id).count() == 2

    db.session.delete(art)
    db.session.commit()

    remaining = (
        db.session.query(ArticuloCodigo).filter_by(articulo_id=art_id).count()
    )
    assert remaining == 0


# ---------------------------------------------------------------------------
# Relationship / backref
# ---------------------------------------------------------------------------


def test_relationship_articulo_codigos_returns_list(db):
    """`articulo.codigos` es una lista de `ArticuloCodigo`."""
    art = _make_articulo(db, codigo="ART_REL")
    art.codigos.append(
        ArticuloCodigo(codigo="REL1", tipo=TipoCodigoArticuloEnum.principal)
    )
    art.codigos.append(
        ArticuloCodigo(codigo="REL2", tipo=TipoCodigoArticuloEnum.alterno)
    )
    db.session.commit()
    db.session.refresh(art)

    assert isinstance(art.codigos, list)
    assert len(art.codigos) == 2
    codigos = {c.codigo for c in art.codigos}
    assert codigos == {"REL1", "REL2"}
    assert all(isinstance(c, ArticuloCodigo) for c in art.codigos)


def test_relationship_codigo_articulo_back_populates(db):
    """`codigo.articulo` devuelve el `Articulo` dueño (back_populates)."""
    art = _make_articulo(db, codigo="ART_BP")
    c = ArticuloCodigo(
        articulo_id=art.id, codigo="BP1", tipo=TipoCodigoArticuloEnum.principal
    )
    db.session.add(c)
    db.session.commit()
    db.session.refresh(c)

    assert c.articulo is not None
    assert isinstance(c.articulo, Articulo)
    assert c.articulo.id == art.id
    assert c.articulo.codigo == "ART_BP"


def test_default_tipo_is_principal(db):
    """`tipo` default es `principal` cuando no se especifica."""
    art = _make_articulo(db, codigo="ART_DEFAULT")
    c = ArticuloCodigo(articulo_id=art.id, codigo="DEFAULT1")
    db.session.add(c)
    db.session.commit()
    db.session.refresh(c)
    assert c.tipo == TipoCodigoArticuloEnum.principal
