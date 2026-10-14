"""Application error types and a single JSON error envelope.

Every failure leaves the API in the same shape:

    {"error": {"code": "list_not_found", "message": "...", "details": {...}}}

which keeps clients from parsing prose and lets Swagger document failures.
"""

from __future__ import annotations

from typing import Any

from fastapi import status


class AppError(Exception):
    """Base class for expected, client-visible failures."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: str = "bad_request"
    message: str = "Некорректный запрос"

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.message = message or self.message
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.details = details or {}
        self.headers = headers or {}
        super().__init__(self.message)

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return {"error": payload}


# --------------------------------------------------------------------- 4xx


class ValidationError(AppError):
    status_code = 422
    code = "validation_error"
    message = "Данные запроса не прошли валидацию"


class AuthenticationError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = "unauthenticated"
    message = "Требуется авторизация"

    def __init__(self, message: str | None = None, **kwargs: Any) -> None:
        headers = kwargs.pop("headers", None) or {"WWW-Authenticate": "Bearer"}
        super().__init__(message, headers=headers, **kwargs)


class InvalidCredentialsError(AuthenticationError):
    code = "invalid_credentials"
    message = "Неверные учетные данные"


class TokenExpiredError(AuthenticationError):
    code = "token_expired"
    message = "Время сессии истекло. Авторизуйтесь заново."


class InvalidTokenError(AuthenticationError):
    code = "invalid_token"
    message = "Недействительный или поврежденный токен"


class PermissionDeniedError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "permission_denied"
    message = "Недостаточно прав для этой операции"


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = "not_found"
    message = "Ресурс не найден"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "conflict"
    message = "Конфликт состояния ресурса"


class LimitExceededError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "limit_exceeded"
    message = "Превышен лимит"


class RateLimitError(AppError):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    code = "rate_limited"
    message = "Слишком много запросов, попробуйте позже"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "payload_too_large"
    message = "Тело запроса слишком большое"


# --------------------------------------------------------------------- 5xx


class InternalError(AppError):
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    code = "internal_error"
    message = "Внутренняя ошибка сервера"


class ServiceUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = "service_unavailable"
    message = "Сервис временно недоступен"


# ------------------------------------------------------------ domain errors


class UserAlreadyExistsError(ConflictError):
    code = "user_already_exists"
    message = "Пользователь с такой почтой уже существует"


class UserDisabledError(AuthenticationError):
    status_code = status.HTTP_403_FORBIDDEN
    code = "user_disabled"
    message = "Учетная запись отключена"


class ListNotFoundError(NotFoundError):
    code = "list_not_found"
    message = "Список не найден или недоступен"


class ItemNotFoundError(NotFoundError):
    code = "item_not_found"
    message = "Товар не найден"


class SystemListError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "system_list_protected"
    message = "Системный список нельзя изменить или удалить"


class InviteInvalidError(AppError):
    code = "invite_invalid"
    message = "Ссылка приглашения недействительна или истекла"


class SuggestionsDisabledError(AppError):
    status_code = status.HTTP_409_CONFLICT
    code = "suggestions_disabled"
    message = "Подсказки ИИ отключены"
