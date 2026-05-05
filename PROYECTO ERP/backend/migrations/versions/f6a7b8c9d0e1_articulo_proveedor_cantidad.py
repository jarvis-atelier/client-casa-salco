"""articulo_proveedor cantidad_por_pack

Agrega la columna `cantidad_por_pack` a `articulo_proveedores` para registrar
la unidad-por-pack del par (articulo, proveedor). Recupera la información que
fue DROPPED en `importacion-xls-legacy` (RELACION.cantidad).

Decisiones (Change B `xls-empaquetados-y-presentaciones` design #559):

- `Numeric(10, 3)` — fuente real tiene 217 cantidades fraccionarias; integer
  perdería precisión, Numeric(10,3) cubre rango (max << 9999) sin overhead.
- NOT NULL con `server_default=sa.text("1")` — semántica natural "1 unidad"
  para los 39215 rows existentes; SQLite ALTER ADD NOT NULL requiere default.
- `op.batch_alter_table` — convención SQLite del proyecto (mirrors
  `c3d4e5f6a7b8`, `e5f6a7b8c9d0`).

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-05-05 23:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "f6a7b8c9d0e1"
down_revision = "e5f6a7b8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("articulo_proveedores", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "cantidad_por_pack",
                sa.Numeric(10, 3),
                nullable=False,
                server_default=sa.text("1"),
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("articulo_proveedores", schema=None) as batch_op:
        batch_op.drop_column("cantidad_por_pack")
