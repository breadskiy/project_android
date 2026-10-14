"""Authentication and account endpoints."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies import (
    CurrentUserDep,
    client_ip,
    enforce_auth_rate_limit,
    user_agent,
)
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    RegisterResponse,
    SessionListResponse,
    TokenResponse,
    UpdateUserSettingsRequest,
    UserSettings,
)
from app.schemas.common import ErrorResponse, MessageResponse
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])

COMMON_ERRORS = {
    400: {"model": ErrorResponse, "description": "Некорректный запрос"},
    422: {"model": ErrorResponse, "description": "Ошибка валидации"},
    429: {"model": ErrorResponse, "description": "Слишком много попыток"},
}


@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация нового пользователя",
    responses={**COMMON_ERRORS, 409: {"model": ErrorResponse, "description": "Email уже занят"}},
)
async def register(payload: RegisterRequest, request: Request) -> RegisterResponse:
    await enforce_auth_rate_limit(request)
    user = await auth_service.register(
        email=payload.email,
        password=payload.password,
        display_name=payload.display_name,
    )
    return RegisterResponse(user=user)  # type: ignore[arg-type]


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход, выдача access- и refresh-токенов",
    responses={**COMMON_ERRORS, 401: {"model": ErrorResponse, "description": "Неверные данные"}},
)
async def login(payload: LoginRequest, request: Request) -> TokenResponse:
    # Keyed by email as well, so one attacker cannot lock out a whole NAT.
    await enforce_auth_rate_limit(request, key_suffix=payload.email)
    tokens = await auth_service.login(
        email=payload.email,
        password=payload.password,
        user_agent=user_agent(request),
        ip_address=client_ip(request),
    )
    return TokenResponse(**tokens)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Обновление access-токена по refresh-токену",
    description=(
        "Refresh-токен одноразовый: при использовании он отзывается и выдается новый. "
        "Повторное использование отозванного токена трактуется как утечка и "
        "приводит к отзыву всех сессий пользователя."
    ),
    responses={**COMMON_ERRORS, 401: {"model": ErrorResponse, "description": "Токен недействителен"}},
)
async def refresh(payload: RefreshRequest, request: Request) -> TokenResponse:
    await enforce_auth_rate_limit(request)
    tokens = await auth_service.refresh(
        refresh_token=payload.refresh_token,
        user_agent=user_agent(request),
        ip_address=client_ip(request),
    )
    return TokenResponse(**tokens)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Выход из аккаунта",
    description="Отзывает переданный refresh-токен либо все сессии пользователя.",
)
async def logout(payload: LogoutRequest, current_user: CurrentUserDep) -> MessageResponse:
    revoked = await auth_service.logout(
        user_id=current_user.id,
        refresh_token=payload.refresh_token,
        all_sessions=payload.all_sessions,
    )
    message = (
        f"Отозвано сессий: {revoked}" if revoked else "Активных сессий для отзыва не найдено"
    )
    return MessageResponse(message=message)


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Смена пароля",
    description="После смены пароля все остальные сессии отзываются.",
    responses={**COMMON_ERRORS, 401: {"model": ErrorResponse, "description": "Текущий пароль неверен"}},
)
async def change_password(
    payload: ChangePasswordRequest, current_user: CurrentUserDep
) -> MessageResponse:
    await auth_service.change_password(
        user_id=current_user.id,
        current_password=payload.current_password,
        new_password=payload.new_password,
    )
    return MessageResponse(message="Пароль изменен, остальные сессии завершены")


@router.get(
    "/sessions",
    response_model=SessionListResponse,
    summary="Активные сессии",
)
async def sessions(current_user: CurrentUserDep) -> SessionListResponse:
    items = await auth_service.list_sessions(current_user.id)
    return SessionListResponse(items=items)  # type: ignore[arg-type]


# --------------------------------------------------------------- account ---

account_router = APIRouter(tags=["account"])


@account_router.get(
    "/me",
    response_model=MeResponse,
    summary="Профиль текущего пользователя",
)
async def me(current_user: CurrentUserDep) -> MeResponse:
    return MeResponse(**await auth_service.get_me(current_user.id))


@account_router.get(
    "/me/settings",
    response_model=UserSettings,
    summary="Настройки пользователя",
    description="Здесь находится переключатель подсказок ИИ.",
)
async def get_settings(current_user: CurrentUserDep) -> UserSettings:
    return UserSettings(**await auth_service.get_settings(current_user.id))


@account_router.patch(
    "/me/settings",
    response_model=UserSettings,
    summary="Изменить настройки",
    description=(
        "`ai_suggestions_enabled=false` полностью отключает подсказки: "
        "они не вычисляются и не запрашиваются у внешних сервисов."
    ),
)
async def update_settings(
    payload: UpdateUserSettingsRequest, current_user: CurrentUserDep
) -> UserSettings:
    updated = await auth_service.update_settings(
        current_user.id,
        ai_suggestions_enabled=payload.ai_suggestions_enabled,
        suggestions_limit=payload.suggestions_limit,
    )
    return UserSettings(**updated)
