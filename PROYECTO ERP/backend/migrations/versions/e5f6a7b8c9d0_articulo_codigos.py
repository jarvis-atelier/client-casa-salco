"""articulo_codigos — tabla 1:N de códigos por artículo + DROP codigo_barras

Crea la tabla `articulo_codigos` (modelo 1:N reemplazo de la columna singular
`articulos.codigo_barras`), backfillea los valores existentes como
`tipo='principal'` y elimina la columna legacy + su índice de `articulos`.

Notas:

- El enum `tipo_codigo_articulo_enum` se carga con los 4 valores desde el
  arranque (principal/alterno/empaquetado/interno) para que Change B
  (xls-empaquetados-y-presentaciones) no requiera una migración de
  extensión.
- El backfill filtra `codigo_barras IS NULL` y `TRIM(codigo_barras) = ''`.
- En SQLite se usa `batch_alter_table` para el drop de columna+index.
- En Postgres el enum se crea/elimina explícitamente; en SQLite se expresa
  como CHECK (manejado automáticamente por SQLAlchemy).
- El downgrade restaura solo los códigos `tipo='principal'`. Los rows
  `alterno`/`empaquetado`/`interno` que pudieran existir post-Change B se
  pierden — comportamiento documentado en spec S10.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-05 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


TIPO_VALUES = ("principal", "alterno", "empaquetado", "interno")


def upgrade():
    bind = op.get_bind()

    # --- 1. Crear el enum (Postgres lo necesita explícito; SQLite lo expresa como CHECK) ---
    tipo_enum = sa.Enum(*TIPO_VALUES, name="tipo_codigo_articulo_enum")
    if bind.dialect.name == "postgresql":
        tipo_enum.create(bind, checkfirst=True)

    # --- 2. Crear la tabla articulo_codigos ---
    op.create_table(
        "articulo_codigos",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("articulo_id", sa.Integer(), nullable=False),
        sa.Column("codigo", sa.String(length=50), nullable=False),
        sa.Column("tipo", tipo_enum, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["articulo_id"], ["articulos.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "articulo_id", "codigo", name="uq_articulo_codigo"
        ),
    )
    with op.batch_alter_table("articulo_codigos", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_articulo_codigos_articulo_id"),
            ["articulo_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_articulo_codigos_codigo"),
            ["codigo"],
            unique=False,
        )

    # --- 3. Backfill: mover codigo_barras existentes a articulo_codigos ---
    # Filtro: solo NOT NULL y no-vacío (tras TRIM). Tipo: 'principal'.
    op.execute(
        """
        INSERT INTO articulo_codigos (articulo_id, codigo, tipo, created_at, updated_at)
        SELECT id, codigo_barras, 'principal', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
        FROM articulos
        WHERE codigo_barras IS NOT NULL AND TRIM(codigo_barras) != ''
        """
    )

    # --- 4. Drop del índice + columna legacy en articulos ---
    with op.batch_alter_table("articulos", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_articulos_codigo_barras"))
        batch_op.drop_column("codigo_barras")


def downgrade():
    bind = op.get_bind()

    # --- 1. Re-añadir la columna codigo_barras en articulos + su índice ---
    with op.batch_alter_table("articulos", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("codigo_barras", sa.String(length=50), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_articulos_codigo_barras"),
            ["codigo_barras"],
            unique=False,
        )

    # --- 2. Restaurar UN principal por articulo (alterno/empaquetado/interno se pierden por diseño S10) ---
    op.execute(
        """
        UPDATE articulos
        SET codigo_barras = (
            SELECT codigo
            FROM articulo_codigos
            WHERE articulo_codigos.articulo_id = articulos.id
              AND articulo_codigos.tipo = 'principal'
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1
            FROM articulo_codigos
            WHERE articulo_codigos.articulo_id = articulos.id
              AND articulo_codigos.tipo = 'principal'
        )
        """
    )

    # --- 3. Drop de la tabla articulo_codigos + sus índices ---
    with op.batch_alter_table("articulo_codigos", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_articulo_codigos_codigo"))
        batch_op.drop_index(batch_op.f("ix_articulo_codigos_articulo_id"))
    op.drop_table("articulo_codigos")

    # --- 4. Postgres: drop del enum (en SQLite no aplica) ---
    if bind.dialect.name == "postgresql":
        sa.Enum(*TIPO_VALUES, name="tipo_codigo_articulo_enum").drop(
            bind, checkfirst=True
        )
