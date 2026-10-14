"""Authentication and account schemas."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import Field, StringConstraints, field_validator

from app.config import settings
from app.schemas.common import DisplayNameStr, ResponseModel, StrictModel

# Deliberately not EmailStr: that requires the optional email-validator
# dependency. This pattern rejects the malformed addresses that matter here.
EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-!#$&'*/=?^`{|}~]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")

PasswordStr = Annotated[str, StringConstraints(min_length=8, max_length=128)]
EmailField = Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=254)]


def _validate_email(value: str) -> str:
    email = value.strip().lower()
    if not EMAIL_RE.fullmatch(email):
        raise ValueError("Некорректный email")
    return email


def _validate_password(value: str) -> str:
    if len(value) < settings.PASSWORD_MIN_LENGTH:
        raise ValueError(f"Пароль должен содержать минимум {settings.PASSWORD_MIN_LENGTH} символов")
    # Reject whitespace-only and trivially weak inputs, but do not impose
    # composition rules: length is what actually matters.
    if not value.strip():
        raise ValueError("Пароль не может состоять из пробелов")
    return value


class RegisterRequest(StrictModel):
    email: EmailField = Field(examples=["user@example.com"])
    password: PasswordStr = Field(examples=["StrongPass123"])
    display_name: DisplayNameStr = Field(examples=["Иван"])

    _validate_email_field = field_validator("email")(_validate_email)
    _validate_password_field = field_validator("password")(_validate_password)


class LoginRequest(StrictModel):
    email: EmailField = Field(examples=["user@example.com"])
    password: PasswordStr = Field(examples=["StrongPass123"])

    _validate_email_field = field_validator("email")(_validate_email)


class RefreshRequest(StrictModel):
    refresh_token: Annotated[str, StringConstraints(min_length=16, max_length=512)]


class LogoutRequest(StrictModel):
    refresh_token: Annotated[str, StringConstraints(min_length=16, max_length=512)] | None = None
    all_sessions: bool = Field(
        default=False,
        description="Отозвать все refresh-токены пользователя, а не только текущий",
    )


class ChangePasswordRequest(StrictModel):
    current_password: PasswordStr
    new_password: PasswordStr

    _validate_new = field_validator("new_password")(_validate_password)


class UserPublic(ResponseModel):
    id: UUID
    email: str = Field(examples=["user@example.com"])
    display_name: str = Field(examples=["Иван"])
    created_at: datetime | None = None
    last_login: datetime | None = None


class RegisterResponse(ResponseModel):
    ok: bool = True
    message: str = Field(default="Регистрация успешна")
    user: UserPublic


class TokenResponse(ResponseModel):
    access_token: str
    refresh_token: str
    token_type: str = Field(default="bearer", examples=["bearer"])
    expires_in: int = Field(description="Время жизни access-токена в секундах", examples=[1800])
    expires_at: datetime
    user: UserPublic


class SessionInfo(ResponseModel):
    id: UUID
    issued_at: datetime
    expires_at: datetime
    user_agent: str | None = None
    current: bool = False


class SessionListResponse(ResponseModel):
    items: list[SessionInfo]


class UserSettings(ResponseModel):
    ai_suggestions_enabled: bool = Field(
        description="Подсказки ИИ «часто покупают вместе». false — полностью отключены",
        examples=[True],
    )
    suggestions_limit: int = Field(ge=1, le=20, examples=[5])
    ai_available: bool = Field(
        description="Доступны ли подсказки на стороне сервера (глобальный переключатель)",
        examples=[True],
    )


class UpdateUserSettingsRequest(StrictModel):
    ai_suggestions_enabled: bool | None = None
    suggestions_limit: int | None = Field(default=None, ge=1, le=20)


class MeResponse(ResponseModel):
    id: UUID
    email: str
    display_name: str
    created_at: datetime | None = None
    last_login: datetime | None = None
    settings: UserSettings
    stats: dict[str, int] = Field(
        default_factory=dict,
        examples=[{"lists_owned": 3, "lists_shared": 1, "items_total": 27}],
    )
