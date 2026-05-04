"""calendario de pagos — compromisos, tarjetas, pagos parciales

Crea las tablas:
- `tarjetas_corporativas` — tarjetas de empresa con cierre/vencimiento
  mensual fijo.
- `compromisos_pago` — vencimientos a pagar (factura compra, ctacte,
  resumen tarjeta, servicios, impuestos).
- `pagos_compromiso` — pagos aplicados (parciales o totales) contra un
  compromiso, con referencia opcional al MovimientoCaja generado.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-25 04:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade():
    # --- tarjetas_corporativas ---
    op.create_table(
        "tarjetas_corporativas",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("nombre", sa.String(length=100), nullable=False),
        sa.Column("banco", sa.String(length=100), nullable=True),
        sa.Column("ultimos_4", sa.String(length=4), nullable=False),
        sa.Column("titular", sa.String(length=150), nullable=True),
        sa.Column("limite_total", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("dia_cierre", sa.Integer(), nullable=False),
        sa.Column("dia_vencimiento", sa.Integer(), nullable=False),
        sa.Column("activa", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )

    # --- compromisos_pago ---
    op.create_table(
        "compromisos_pago",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column(
            "tipo",
            sa.Enum(
                "factura_compra",
                "cuenta_corriente_proveedor",
                "tarjeta_corporativa",
                "servicio",
                "impuesto",
                "otro",
                name="tipo_compromiso_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "estado",
            sa.Enum(
                "pendiente",
                "parcial",
                "pagado",
                "vencido",
                "cancelado",
                name="estado_compromiso_enum",
            ),
            nullable=False,
        ),
        sa.Column("descripcion", sa.String(length=255), nullable=False),
        sa.Column("monto_total", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("monto_pagado", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("fecha_emision", sa.Date(), nullable=True),
        sa.Column("fecha_vencimiento", sa.Date(), nullable=False),
        sa.Column("fecha_pago_real", sa.Date(), nullable=True),
        sa.Column("proveedor_id", sa.Integer(), nullable=True),
        sa.Column("factura_id", sa.Integer(), nullable=True),
        sa.Column("tarjeta_id", sa.Integer(), nullable=True),
        sa.Column("sucursal_id", sa.Integer(), nullable=True),
        sa.Column("creado_por_user_id", sa.Integer(), nullable=False),
        sa.Column("pagado_por_user_id", sa.Integer(), nullable=True),
        sa.Column("nota", sa.Text(), nullable=True),
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
            ["proveedor_id"], ["proveedores.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["factura_id"], ["facturas.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["tarjeta_id"], ["tarjetas_corporativas.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["sucursal_id"], ["sucursales.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["creado_por_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["pagado_por_user_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("compromisos_pago", schema=None) as batch_op:
        batch_op.create_index(
            "ix_compromisos_pago_tipo", ["tipo"], unique=False
        )
        batch_op.create_index(
            "ix_compromisos_pago_estado", ["estado"], unique=False
        )
        batch_op.create_index(
            "ix_compromisos_pago_fecha_vencimiento",
            ["fecha_vencimiento"],
            unique=False,
        )
        batch_op.create_index(
            "ix_compromisos_pago_proveedor_id", ["proveedor_id"], unique=False
        )
        batch_op.create_index(
            "ix_compromisos_pago_factura_id", ["factura_id"], unique=False
        )
        batch_op.create_index(
            "ix_compromisos_pago_tarjeta_id", ["tarjeta_id"], unique=False
        )
        batch_op.create_index(
            "ix_compromisos_pago_sucursal_id", ["sucursal_id"], unique=False
        )

    # --- pagos_compromiso ---
    op.create_table(
        "pagos_compromiso",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("compromiso_id", sa.Integer(), nullable=False),
        sa.Column("fecha_pago", sa.Date(), nullable=False),
        sa.Column("monto", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("medio_pago", sa.String(length=50), nullable=False),
        sa.Column("referencia", sa.String(length=200), nullable=True),
        sa.Column("movimiento_caja_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
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
            ["compromiso_id"], ["compromisos_pago.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["movimiento_caja_id"], ["movimientos_caja.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("pagos_compromiso", schema=None) as batch_op:
        batch_op.create_index(
            "ix_pagos_compromiso_compromiso_id", ["compromiso_id"], unique=False
        )
        batch_op.create_index(
            "ix_pagos_compromiso_fecha_pago", ["fecha_pago"], unique=False
        )


def downgrade():
    with op.batch_alter_table("pagos_compromiso", schema=None) as batch_op:
        batch_op.drop_index("ix_pagos_compromiso_fecha_pago")
        batch_op.drop_index("ix_pagos_compromiso_compromiso_id")
    op.drop_table("pagos_compromiso")

    with op.batch_alter_table("compromisos_pago", schema=None) as batch_op:
        batch_op.drop_index("ix_compromisos_pago_sucursal_id")
        batch_op.drop_index("ix_compromisos_pago_tarjeta_id")
        batch_op.drop_index("ix_compromisos_pago_factura_id")
        batch_op.drop_index("ix_compromisos_pago_proveedor_id")
        batch_op.drop_index("ix_compromisos_pago_fecha_vencimiento")
        batch_op.drop_index("ix_compromisos_pago_estado")
        batch_op.drop_index("ix_compromisos_pago_tipo")
    op.drop_table("compromisos_pago")

    op.drop_table("tarjetas_corporativas")

    sa.Enum(name="estado_compromiso_enum").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="tipo_compromiso_enum").drop(op.get_bind(), checkfirst=False)
