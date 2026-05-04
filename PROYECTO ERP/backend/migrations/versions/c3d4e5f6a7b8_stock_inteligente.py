"""stock inteligente — opcion C

Agrega:
- Defaults globales en `articulos`: stock_minimo_default, stock_maximo_default,
  punto_reorden_default, lead_time_dias_default.
- Columnas en `stock_sucursal`: stock_minimo, stock_maximo, punto_reorden,
  lead_time_dias, stock_optimo_calculado, ultima_recalculacion.
- Columna `lead_time_dias_default` en `proveedores`.
- Nuevos valores del Enum tipo_alerta_enum: stock_bajo_minimo, sobrestock,
  rotacion_lenta, rotacion_rapida_faltante.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-25 03:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c3d4e5f6a7b8"
down_revision = "b2c3d4e5f6a7"
branch_labels = None
depends_on = None


def upgrade():
    # --- articulos: defaults globales ---
    with op.batch_alter_table("articulos", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("stock_minimo_default", sa.Numeric(precision=14, scale=4), nullable=True)
        )
        batch_op.add_column(
            sa.Column("stock_maximo_default", sa.Numeric(precision=14, scale=4), nullable=True)
        )
        batch_op.add_column(
            sa.Column("punto_reorden_default", sa.Numeric(precision=14, scale=4), nullable=True)
        )
        batch_op.add_column(
            sa.Column("lead_time_dias_default", sa.Integer(), nullable=True)
        )

    # --- proveedores: lead_time default ---
    with op.batch_alter_table("proveedores", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("lead_time_dias_default", sa.Integer(), nullable=True)
        )

    # --- stock_sucursal: overrides + calculados ---
    with op.batch_alter_table("stock_sucursal", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("stock_minimo", sa.Numeric(precision=14, scale=4), nullable=True)
        )
        batch_op.add_column(
            sa.Column("stock_maximo", sa.Numeric(precision=14, scale=4), nullable=True)
        )
        batch_op.add_column(
            sa.Column("punto_reorden", sa.Numeric(precision=14, scale=4), nullable=True)
        )
        batch_op.add_column(
            sa.Column("lead_time_dias", sa.Integer(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("stock_optimo_calculado", sa.Numeric(precision=14, scale=4), nullable=True)
        )
        batch_op.add_column(
            sa.Column("ultima_recalculacion", sa.DateTime(timezone=True), nullable=True)
        )

    # --- ampliar enum tipo_alerta_enum (PG: ALTER TYPE; SQLite: noop, enum es CHECK) ---
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Postgres requiere ALTER TYPE para nuevos valores.
        op.execute("ALTER TYPE tipo_alerta_enum ADD VALUE IF NOT EXISTS 'stock_bajo_minimo'")
        op.execute("ALTER TYPE tipo_alerta_enum ADD VALUE IF NOT EXISTS 'sobrestock'")
        op.execute("ALTER TYPE tipo_alerta_enum ADD VALUE IF NOT EXISTS 'rotacion_lenta'")
        op.execute("ALTER TYPE tipo_alerta_enum ADD VALUE IF NOT EXISTS 'rotacion_rapida_faltante'")
    # En SQLite los enums son CHECK constraints; SQLAlchemy igual los acepta
    # como string al leer. Para no romper la CHECK existente la rebuildeamos:
    if bind.dialect.name == "sqlite":
        # Rebuild de la CHECK constraint via batch_alter_table (recrea la tabla)
        new_enum = sa.Enum(
            "pago_duplicado",
            "factura_compra_repetida",
            "items_repetidos_diff_nro",
            "anulaciones_frecuentes",
            "ajuste_stock_sospechoso",
            "nota_credito_sospechosa",
            "venta_fuera_horario",
            "descuento_excesivo",
            "vencimiento_proximo",
            "stock_bajo_minimo",
            "sobrestock",
            "rotacion_lenta",
            "rotacion_rapida_faltante",
            name="tipo_alerta_enum",
        )
        with op.batch_alter_table("alertas", schema=None) as batch_op:
            batch_op.alter_column(
                "tipo",
                existing_type=sa.String(length=50),
                type_=new_enum,
                existing_nullable=False,
            )


def downgrade():
    with op.batch_alter_table("stock_sucursal", schema=None) as batch_op:
        batch_op.drop_column("ultima_recalculacion")
        batch_op.drop_column("stock_optimo_calculado")
        batch_op.drop_column("lead_time_dias")
        batch_op.drop_column("punto_reorden")
        batch_op.drop_column("stock_maximo")
        batch_op.drop_column("stock_minimo")

    with op.batch_alter_table("proveedores", schema=None) as batch_op:
        batch_op.drop_column("lead_time_dias_default")

    with op.batch_alter_table("articulos", schema=None) as batch_op:
        batch_op.drop_column("lead_time_dias_default")
        batch_op.drop_column("punto_reorden_default")
        batch_op.drop_column("stock_maximo_default")
        batch_op.drop_column("stock_minimo_default")

    # Postgres: no podemos quitar valores de un Enum sin recrear el tipo.
    # Lo dejamos — la app vieja simplemente no usa esos valores.
