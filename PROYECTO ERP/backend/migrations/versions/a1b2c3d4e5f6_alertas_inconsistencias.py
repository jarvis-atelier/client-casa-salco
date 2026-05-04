"""alertas inconsistencias

Revision ID: a1b2c3d4e5f6
Revises: f06aff01a31a
Create Date: 2026-04-25 00:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "f06aff01a31a"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "alertas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "pago_duplicado",
                "factura_compra_repetida",
                "items_repetidos_diff_nro",
                "anulaciones_frecuentes",
                "ajuste_stock_sospechoso",
                "nota_credito_sospechosa",
                "venta_fuera_horario",
                "descuento_excesivo",
                name="tipo_alerta_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "severidad",
            sa.Enum("baja", "media", "alta", "critica", name="severidad_enum"),
            nullable=False,
        ),
        sa.Column(
            "estado",
            sa.Enum(
                "nueva",
                "en_revision",
                "descartada",
                "confirmada",
                "resuelta",
                name="estado_alerta_enum",
            ),
            nullable=False,
        ),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("descripcion", sa.Text(), nullable=False),
        sa.Column("contexto", sa.JSON(), nullable=False),
        sa.Column("factura_id", sa.Integer(), nullable=True),
        sa.Column("user_relacionado_id", sa.Integer(), nullable=True),
        sa.Column("proveedor_id", sa.Integer(), nullable=True),
        sa.Column("sucursal_id", sa.Integer(), nullable=True),
        sa.Column("detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("nota_resolucion", sa.Text(), nullable=True),
        sa.Column("deteccion_hash", sa.String(length=64), nullable=False),
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
            ["factura_id"], ["facturas.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_relacionado_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["proveedor_id"], ["proveedores.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["sucursal_id"], ["sucursales.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("alertas", schema=None) as batch_op:
        batch_op.create_index("ix_alertas_tipo", ["tipo"], unique=False)
        batch_op.create_index("ix_alertas_severidad", ["severidad"], unique=False)
        batch_op.create_index("ix_alertas_estado", ["estado"], unique=False)
        batch_op.create_index(
            "ix_alertas_factura_id", ["factura_id"], unique=False
        )
        batch_op.create_index(
            "ix_alertas_user_relacionado_id",
            ["user_relacionado_id"],
            unique=False,
        )
        batch_op.create_index(
            "ix_alertas_proveedor_id", ["proveedor_id"], unique=False
        )
        batch_op.create_index(
            "ix_alertas_sucursal_id", ["sucursal_id"], unique=False
        )
        batch_op.create_index(
            "ix_alertas_detected_at", ["detected_at"], unique=False
        )
        batch_op.create_index(
            "ix_alertas_deteccion_hash",
            ["deteccion_hash"],
            unique=True,
        )


def downgrade():
    with op.batch_alter_table("alertas", schema=None) as batch_op:
        batch_op.drop_index("ix_alertas_deteccion_hash")
        batch_op.drop_index("ix_alertas_detected_at")
        batch_op.drop_index("ix_alertas_sucursal_id")
        batch_op.drop_index("ix_alertas_proveedor_id")
        batch_op.drop_index("ix_alertas_user_relacionado_id")
        batch_op.drop_index("ix_alertas_factura_id")
        batch_op.drop_index("ix_alertas_estado")
        batch_op.drop_index("ix_alertas_severidad")
        batch_op.drop_index("ix_alertas_tipo")
    op.drop_table("alertas")
    sa.Enum(name="tipo_alerta_enum").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="severidad_enum").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="estado_alerta_enum").drop(op.get_bind(), checkfirst=False)
