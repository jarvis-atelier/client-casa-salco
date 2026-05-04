"""ocr comprobantes

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-04-24 16:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "comprobantes_ocr",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("archivo_path", sa.String(length=500), nullable=False),
        sa.Column("archivo_size_bytes", sa.Integer(), nullable=False),
        sa.Column("archivo_mime", sa.String(length=50), nullable=False),
        sa.Column(
            "estado",
            sa.Enum(
                "pendiente",
                "procesando",
                "extraido",
                "confirmado",
                "descartado",
                "error",
                name="estado_ocr_enum",
            ),
            nullable=False,
        ),
        sa.Column(
            "tipo_detectado",
            sa.Enum(
                "factura",
                "remito",
                "presupuesto",
                "desconocido",
                name="tipo_comprobante_ocr_enum",
            ),
            nullable=False,
        ),
        sa.Column("letra", sa.String(length=2), nullable=True),
        sa.Column("confianza", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("proveedor_nombre_raw", sa.String(length=255), nullable=True),
        sa.Column("proveedor_cuit_raw", sa.String(length=20), nullable=True),
        sa.Column("proveedor_id_match", sa.Integer(), nullable=True),
        sa.Column("numero_comprobante", sa.String(length=40), nullable=True),
        sa.Column("fecha_comprobante", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("iva_total", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("total", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("items_extraidos", sa.JSON(), nullable=False),
        sa.Column("raw_response", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=False),
        sa.Column("sucursal_id", sa.Integer(), nullable=True),
        sa.Column("factura_creada_id", sa.Integer(), nullable=True),
        sa.Column("duracion_extraccion_ms", sa.Integer(), nullable=True),
        sa.Column("modelo_ia_usado", sa.String(length=80), nullable=True),
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
            ["proveedor_id_match"], ["proveedores.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["sucursal_id"], ["sucursales.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["factura_creada_id"], ["facturas.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("comprobantes_ocr", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_comprobantes_ocr_estado"), ["estado"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_comprobantes_ocr_proveedor_id_match"),
            ["proveedor_id_match"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_comprobantes_ocr_uploaded_by_user_id"),
            ["uploaded_by_user_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_comprobantes_ocr_sucursal_id"),
            ["sucursal_id"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_comprobantes_ocr_factura_creada_id"),
            ["factura_creada_id"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("comprobantes_ocr", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_comprobantes_ocr_factura_creada_id"))
        batch_op.drop_index(batch_op.f("ix_comprobantes_ocr_sucursal_id"))
        batch_op.drop_index(batch_op.f("ix_comprobantes_ocr_uploaded_by_user_id"))
        batch_op.drop_index(batch_op.f("ix_comprobantes_ocr_proveedor_id_match"))
        batch_op.drop_index(batch_op.f("ix_comprobantes_ocr_estado"))
    op.drop_table("comprobantes_ocr")
    sa.Enum(name="tipo_comprobante_ocr_enum").drop(op.get_bind(), checkfirst=False)
    sa.Enum(name="estado_ocr_enum").drop(op.get_bind(), checkfirst=False)
