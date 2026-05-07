"""Schemas Pydantic para User."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.user import RolEnum


class UserBase(BaseModel):
    email: EmailStr
    nombre: str = Field(min_length=1, max_length=200)
    rol: RolEnum = RolEnum.cajero
    sucursal_id: int | None = None
    activo: bool = True


class UserCreate(UserBase):
    password: str = Field(min_length=6, max_length=128)


class UserUpdate(BaseModel):
    nombre: str | None = Field(default=None, min_length=1, max_length=200)
    rol: RolEnum | None = None
    sucursal_id: int | None = None
    activo: bool | None = None
    password: str | None = Field(default=None, min_length=6, max_length=128)


class UserOut(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserOut
