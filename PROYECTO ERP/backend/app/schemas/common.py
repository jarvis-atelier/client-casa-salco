"""Schemas compartidos (paginación, errores)."""
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    page: int
    per_page: int
    total: int
    pages: int


class ErrorResponse(BaseModel):
    error: str
    code: str | None = None
    details: dict | list | None = None
