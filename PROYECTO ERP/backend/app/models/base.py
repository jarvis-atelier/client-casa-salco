"""Base declarativa + mixins comunes para todos los modelos."""
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db

# Reexportamos el Base de Flask-SQLAlchemy (que internamente es un DeclarativeBase)
# para que todos los modelos se registren en el mismo metadata.
Base = db.Model


class TimestampMixin:
    """Agrega created_at y updated_at manejados por la DB."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """Marca lógica de borrado sin perder el registro (auditoría)."""

    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None
