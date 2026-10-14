"""FastAPI dependencies: authentication, pagination, rate limiting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Query, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import settings
from app.core.errors import AuthenticationError, InvalidTokenError, RateLimitError
from app.core.rate_limit import RateLimiter
from app.core.security import decode_access_token
from app.db.pool import run_in_thread
from app.repositories import users as users_repo

# auto_error=False so a missing header produces our JSON envelope rather than
# Starlette's default {"detail": "Not authenticated"}.
bearer_scheme = HTTPBearer(auto_error=False, description="JWT access-токен")

auth_limiter = RateLimiter(
    settings.AUTH_RATE_LIMIT_REQUESTS,
    settings.RATE_LIMIT_WINDOW,
    name="auth",
)


@dataclass(slots=True)
class CurrentUser:
    id: str
    email: str
    display_name: str

    @property
    def uuid(self) -> str:
        return self.id


def client_ip(request: Request) -> str:
    """Best-effort client address.

    ``X-Forwarded-For`` is honoured only when the deployment explicitly says it
    sits behind a trusted proxy; otherwise clients could spoof it to bypass
    rate limits.
    """
    if settings.TRUST_PROXY_HEADERS:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def get_current_user(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> CurrentUser:
    """Validate the bearer token and confirm the account is still active.

    The DB check on every request is deliberate: a JWT alone cannot express
    "this account was just disabled", and a 30-minute window of access for a
    banned user is not acceptable.
    """
    if credentials is None or not credentials.credentials.strip():
        raise AuthenticationError("Требуется Bearer-токен")

    token = credentials.credentials.strip()
    if len(token) > 4096:
        raise InvalidTokenError("Токен слишком длинный")

    payload = decode_access_token(token)
    user_id = str(payload["sub"])

    user = await run_in_thread(users_repo.get_by_id, user_id)
    if user is None:
        raise InvalidTokenError("Пользователь не найден")
    if not user["is_active"]:
        from app.core.errors import UserDisabledError

        raise UserDisabledError()

    request.state.user_id = user_id
    return CurrentUser(
        id=user_id,
        email=user["email"],
        display_name=user["display_name"],
    )


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


async def enforce_auth_rate_limit(request: Request, key_suffix: str = "") -> None:
    """Stricter limit for credential endpoints (login, register, refresh)."""
    key = f"{request.url.path}:{client_ip(request)}:{key_suffix}"
    allowed, retry_after = await auth_limiter.check(key)
    if not allowed:
        raise RateLimitError(
            "Слишком много попыток, попробуйте позже",
            details={"retry_after": retry_after},
            headers={"Retry-After": str(retry_after)},
        )


@dataclass(slots=True)
class Pagination:
    limit: int
    offset: int


async def pagination_params(
    limit: Annotated[int, Query(ge=1, le=200, description="Размер страницы")] = 50,
    offset: Annotated[int, Query(ge=0, description="Смещение")] = 0,
) -> Pagination:
    return Pagination(limit=limit, offset=offset)


PaginationDep = Annotated[Pagination, Depends(pagination_params)]


def user_agent(request: Request) -> str | None:
    value = request.headers.get("user-agent")
    return value[:512] if value else None
