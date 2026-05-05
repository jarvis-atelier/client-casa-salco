"""Schemas Pydantic para ArticuloCodigo."""
from pydantic import BaseModel, ConfigDict, Field

from app.models.articulo_codigo import TipoCodigoArticuloEnum


class ArticuloCodigoBase(BaseModel):
    codigo: str = Field(min_length=1, max_length=50)
    tipo: TipoCodigoArticuloEnum = TipoCodigoArticuloEnum.principal


class ArticuloCodigoCreate(ArticuloCodigoBase):
    articulo_id: int


class ArticuloCodigoOut(ArticuloCodigoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    articulo_id: int
