"""Authentication and account services."""

from __future__ import annotations

from typing import Any

import psycopg

from app.config import settings
from app.core.errors import (
    InvalidCredentialsError,
    InvalidTokenError,
    UserAlreadyExistsError,
    UserDisabledError,
)
from app.core.logging import get_logger
from app.core.normalization import clean_display_name
from app.core.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    refresh_token_expiry,
    utcnow,
    verify_password,
    waste_password_time,
)
from app.db.pool import Row, run_in_thread
from app.repositories import lists as lists_repo
from app.repositories import suggestions as suggestions_repo
from app.repositories import users as users_repo

logger = get_logger("smartsupply.auth")


def _public_user(row: Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "email": row["email"],
        "display_name": row["display_name"],
        "created_at": row.get("created_at"),
        "last_login": row.get("last_login"),
    }


# ------------------------------------------------------------- registration


def _register_sync(*, email: str, password: str, display_name: str) -> dict[str, Any]:
    clean_name = clean_display_name(display_name)
    if not clean_name:
        raise InvalidCredentialsError("Имя не может быть пустым", code="invalid_display_name")

    try:
        created = users_repo.create(
            email=email,
            password_hash=hash_password(password),
            display_name=clean_name,
        )
    except psycopg.errors.UniqueViolation as exc:
        raise UserAlreadyExistsError() from exc

    user_id = str(created["id"])
    # Every account starts with the protected favourites list, matching the
    # behaviour of the original CLI version.
    lists_repo.ensure_favorites(user_id)
    suggestions_repo.log_event(
        user_id=user_id,
        event_type="view",
        entity_type="user",
        entity_id=user_id,
        metadata={"action": "register"},
    )
    return _public_user(created)


async def register(*, email: str, password: str, display_name: str) -> dict[str, Any]:
    return await run_in_thread(
        _register_sync, email=email, password=password, display_name=display_name
    )


# --------------------------------------------------------------------- login


def _login_sync(
    *,
    email: str,
    password: str,
    user_agent: str | None,
    ip_address: str | None,
) -> dict[str, Any]:
    user = users_repo.get_by_email(email)

    if user is None:
        # Spend the same CPU as a real verification so response time does not
        # reveal whether the address is registered.
        waste_password_time()
        raise InvalidCredentialsError()

    if not verify_password(password, user["password_hash"]):
        raise InvalidCredentialsError()

    if not user["is_active"]:
        raise UserDisabledError()

    user_id = str(user["id"])

    # Transparently upgrade the stored hash when the cost setting grows.
    if needs_rehash(user["password_hash"]):
        users_repo.update_password_hash(user_id, hash_password(password))
        logger.info("Upgraded password hash cost for user %s", user_id)

    now = utcnow()
    users_repo.touch_last_login(user_id, now)
    lists_repo.ensure_favorites(user_id)

    return _issue_tokens(
        user_id=user_id,
        email=user["email"],
        display_name=user["display_name"],
        created_at=user.get("created_at"),
        last_login=now,
        user_agent=user_agent,
        ip_address=ip_address,
    )


def _issue_tokens(
    *,
    user_id: str,
    email: str,
    display_name: str,
    created_at: Any,
    last_login: Any,
    user_agent: str | None,
    ip_address: str | None,
) -> dict[str, Any]:
    access_token, expires_at = create_access_token(
        user_id=user_id, display_name=display_name, email=email
    )
    refresh_token = generate_refresh_token()
    users_repo.create_refresh_token(
        user_id=user_id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=refresh_token_expiry(),
        user_agent=user_agent,
        ip_address=ip_address,
    )

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_EXPIRE_MINUTES * 60,
        "expires_at": expires_at,
        "user": {
            "id": user_id,
            "email": email,
            "display_name": display_name,
            "created_at": created_at,
            "last_login": last_login,
        },
    }


async def login(
    *,
    email: str,
    password: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    return await run_in_thread(
        _login_sync,
        email=email,
        password=password,
        user_agent=user_agent,
        ip_address=ip_address,
    )


# ------------------------------------------------------------------- refresh


def _refresh_sync(
    *,
    refresh_token: str,
    user_agent: str | None,
    ip_address: str | None,
) -> dict[str, Any]:
    token_hash = hash_refresh_token(refresh_token)
    stored = users_repo.find_active_refresh_token(token_hash)

    if stored is None:
        raise InvalidTokenError("Refresh-токен не найден")

    if not stored["is_active"]:
        raise UserDisabledError()

    if stored["revoked_at"] is not None:
        # A revoked token being replayed means the token leaked: drop every
        # session for that user rather than silently issuing a new pair.
        users_repo.revoke_all_refresh_tokens(str(stored["user_id"]))
        logger.warning(
            "Refresh token replay detected for user %s; all sessions revoked",
            stored["user_id"],
        )
        raise InvalidTokenError("Refresh-токен отозван. Авторизуйтесь заново.")

    if stored["expires_at"] <= utcnow():
        raise InvalidTokenError("Refresh-токен истек. Авторизуйтесь заново.")

    user_id = str(stored["user_id"])
    new_refresh = generate_refresh_token()
    rotated = users_repo.rotate_refresh_token(
        old_token_hash=token_hash,
        user_id=user_id,
        new_token_hash=hash_refresh_token(new_refresh),
        expires_at=refresh_token_expiry(),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    if rotated is None:
        raise InvalidTokenError("Refresh-токен больше не действителен")

    access_token, expires_at = create_access_token(
        user_id=user_id,
        display_name=stored["display_name"],
        email=stored["email"],
    )

    return {
        "access_token": access_token,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "expires_in": settings.JWT_EXPIRE_MINUTES * 60,
        "expires_at": expires_at,
        "user": {
            "id": user_id,
            "email": stored["email"],
            "display_name": stored["display_name"],
            "created_at": None,
            "last_login": None,
        },
    }


async def refresh(
    *,
    refresh_token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    return await run_in_thread(
        _refresh_sync,
        refresh_token=refresh_token,
        user_agent=user_agent,
        ip_address=ip_address,
    )


# -------------------------------------------------------------------- logout


def _logout_sync(*, user_id: str, refresh_token: str | None, all_sessions: bool) -> int:
    if all_sessions:
        return users_repo.revoke_all_refresh_tokens(user_id)
    if refresh_token:
        return users_repo.revoke_refresh_token(hash_refresh_token(refresh_token))
    return 0


async def logout(
    *, user_id: str, refresh_token: str | None = None, all_sessions: bool = False
) -> int:
    return await run_in_thread(
        _logout_sync,
        user_id=user_id,
        refresh_token=refresh_token,
        all_sessions=all_sessions,
    )


# ------------------------------------------------------------------ password


def _change_password_sync(*, user_id: str, current_password: str, new_password: str) -> None:
    user = users_repo.get_by_id(user_id)
    if user is None:
        raise InvalidCredentialsError()
    if not verify_password(current_password, user["password_hash"]):
        raise InvalidCredentialsError("Текущий пароль неверен")

    users_repo.update_password_hash(user_id, hash_password(new_password))
    # Changing a password ends every other session.
    users_repo.revoke_all_refresh_tokens(user_id)


async def change_password(*, user_id: str, current_password: str, new_password: str) -> None:
    await run_in_thread(
        _change_password_sync,
        user_id=user_id,
        current_password=current_password,
        new_password=new_password,
    )


# ------------------------------------------------------------------ profile


def _me_sync(user_id: str) -> dict[str, Any]:
    user = users_repo.get_by_id(user_id)
    if user is None:
        raise InvalidTokenError("Пользователь не найден")

    prefs = users_repo.get_preferences(user_id)
    stats = users_repo.get_stats(user_id)

    return {
        "id": user["id"],
        "email": user["email"],
        "display_name": user["display_name"],
        "created_at": user.get("created_at"),
        "last_login": user.get("last_login"),
        "settings": {
            "ai_suggestions_enabled": prefs["ai_suggestions_enabled"],
            "suggestions_limit": prefs["suggestions_limit"],
            "ai_available": settings.AI_SUGGESTIONS_ENABLED,
        },
        "stats": {
            "lists_owned": int(stats["lists_owned"]),
            "lists_shared": int(stats["lists_shared"]),
            "items_total": int(stats["items_total"]),
        },
    }


async def get_me(user_id: str) -> dict[str, Any]:
    return await run_in_thread(_me_sync, user_id)


def _settings_sync(user_id: str) -> dict[str, Any]:
    prefs = users_repo.get_preferences(user_id)
    return {
        "ai_suggestions_enabled": prefs["ai_suggestions_enabled"],
        "suggestions_limit": prefs["suggestions_limit"],
        "ai_available": settings.AI_SUGGESTIONS_ENABLED,
    }


async def get_settings(user_id: str) -> dict[str, Any]:
    return await run_in_thread(_settings_sync, user_id)


def _update_settings_sync(
    user_id: str,
    *,
    ai_suggestions_enabled: bool | None,
    suggestions_limit: int | None,
) -> dict[str, Any]:
    prefs = users_repo.update_preferences(
        user_id,
        ai_suggestions_enabled=ai_suggestions_enabled,
        suggestions_limit=suggestions_limit,
    )
    return {
        "ai_suggestions_enabled": prefs["ai_suggestions_enabled"],
        "suggestions_limit": prefs["suggestions_limit"],
        "ai_available": settings.AI_SUGGESTIONS_ENABLED,
    }


async def update_settings(
    user_id: str,
    *,
    ai_suggestions_enabled: bool | None = None,
    suggestions_limit: int | None = None,
) -> dict[str, Any]:
    return await run_in_thread(
        _update_settings_sync,
        user_id,
        ai_suggestions_enabled=ai_suggestions_enabled,
        suggestions_limit=suggestions_limit,
    )


# ------------------------------------------------------------------ sessions


def _sessions_sync(user_id: str, current_refresh_hash: str | None) -> list[dict[str, Any]]:
    rows = users_repo.list_sessions(user_id)
    return [
        {
            "id": row["id"],
            "issued_at": row["issued_at"],
            "expires_at": row["expires_at"],
            "user_agent": row["user_agent"],
            "current": current_refresh_hash is not None
            and row["token_hash"] == current_refresh_hash,
        }
        for row in rows
    ]


async def list_sessions(user_id: str, *, current_refresh_token: str | None = None) -> list[dict[str, Any]]:
    current_hash = hash_refresh_token(current_refresh_token) if current_refresh_token else None
    return await run_in_thread(_sessions_sync, user_id, current_hash)
