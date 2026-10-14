"""User, session and preference persistence."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

import psycopg
from psycopg.types.json import Json

from app.core.security import utcnow
from app.db.pool import Row, connection, execute, fetch_all, fetch_one, fetch_value

USER_COLUMNS = """
    id, email, display_name, password_hash, is_active, email_verified,
    phone, locale, timezone, profile, preferred_store_id,
    created_at, last_login
"""


# ----------------------------------------------------------------- queries


def get_by_email(email: str) -> Row | None:
    return fetch_one(
        f"SELECT {USER_COLUMNS} FROM users WHERE lower(email) = lower(%s) LIMIT 1",
        (email,),
    )


def get_by_id(user_id: str) -> Row | None:
    return fetch_one(f"SELECT {USER_COLUMNS} FROM users WHERE id = %s", (user_id,))


def email_exists(email: str) -> bool:
    return fetch_value("SELECT 1 FROM users WHERE lower(email) = lower(%s) LIMIT 1", (email,)) == 1


# ------------------------------------------------------------------ writes


def create(
    *,
    email: str,
    password_hash: str,
    display_name: str,
    phone: str = "",
    locale: str = "ru-RU",
    timezone_value: str = "Europe/Moscow",
    profile: dict[str, Any] | None = None,
) -> Row:
    """Insert a user. Raises ``psycopg.errors.UniqueViolation`` on duplicates."""
    user_id = str(uuid4())
    now = utcnow()

    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO users (
                    id, email, password_hash, display_name, phone, locale,
                    timezone, profile, is_active, email_verified,
                    created_at, last_login
                )
                VALUES (
                    %(id)s, %(email)s, %(password_hash)s, %(display_name)s,
                    %(phone)s, %(locale)s, %(timezone)s, %(profile)s,
                    true, false, %(now)s, NULL
                )
                RETURNING id, email, display_name, created_at, last_login
                """,
                {
                    "id": user_id,
                    "email": email.lower(),
                    "password_hash": password_hash,
                    "display_name": display_name,
                    "phone": phone,
                    "locale": locale,
                    "timezone": timezone_value,
                    "profile": Json(profile or {}),
                    "now": now,
                },
            )
            row = cur.fetchone()

            # Every user gets a preferences row, so the AI toggle always exists.
            cur.execute(
                """
                INSERT INTO user_preferences (user_id, ai_suggestions_enabled, suggestions_limit)
                VALUES (%s, true, 5)
                ON CONFLICT (user_id) DO NOTHING
                """,
                (user_id,),
            )

    assert row is not None
    return row


def touch_last_login(user_id: str, when: datetime | None = None) -> None:
    execute("UPDATE users SET last_login = %s WHERE id = %s", (when or utcnow(), user_id))


def update_password_hash(user_id: str, password_hash: str) -> None:
    execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))


# ------------------------------------------------------------ preferences


def get_preferences(user_id: str) -> Row:
    row = fetch_one(
        """
        SELECT ai_suggestions_enabled, suggestions_limit
        FROM user_preferences
        WHERE user_id = %s
        """,
        (user_id,),
    )
    if row is not None:
        return row

    # Backfill for accounts created before the preferences table was used.
    created = fetch_one(
        """
        INSERT INTO user_preferences (user_id, ai_suggestions_enabled, suggestions_limit)
        VALUES (%s, true, 5)
        ON CONFLICT (user_id) DO UPDATE SET user_id = EXCLUDED.user_id
        RETURNING ai_suggestions_enabled, suggestions_limit
        """,
        (user_id,),
    )
    return created or {"ai_suggestions_enabled": True, "suggestions_limit": 5}


def update_preferences(
    user_id: str,
    *,
    ai_suggestions_enabled: bool | None = None,
    suggestions_limit: int | None = None,
) -> Row:
    row = fetch_one(
        """
        INSERT INTO user_preferences (user_id, ai_suggestions_enabled, suggestions_limit)
        VALUES (
            %(user_id)s,
            COALESCE(%(ai)s, true),
            COALESCE(%(limit)s, 5)
        )
        ON CONFLICT (user_id) DO UPDATE
        SET ai_suggestions_enabled =
                COALESCE(%(ai)s, user_preferences.ai_suggestions_enabled),
            suggestions_limit =
                COALESCE(%(limit)s, user_preferences.suggestions_limit),
            updated_at = now()
        RETURNING ai_suggestions_enabled, suggestions_limit
        """,
        {"user_id": user_id, "ai": ai_suggestions_enabled, "limit": suggestions_limit},
    )
    assert row is not None
    return row


def get_stats(user_id: str) -> Row:
    row = fetch_one(
        """
        SELECT
            (SELECT count(*) FROM shopping_lists WHERE user_id = %(uid)s) AS lists_owned,
            (SELECT count(*)
               FROM shopping_list_members m
               JOIN shopping_lists l ON l.id = m.shopping_list_id
              WHERE m.user_id = %(uid)s AND l.user_id <> %(uid)s) AS lists_shared,
            (SELECT count(*)
               FROM shopping_list_items i
               JOIN shopping_lists l ON l.id = i.shopping_list_id
              WHERE l.user_id = %(uid)s) AS items_total
        """,
        {"uid": user_id},
    )
    return row or {"lists_owned": 0, "lists_shared": 0, "items_total": 0}


# -------------------------------------------------------- refresh sessions


def create_refresh_token(
    *,
    user_id: str,
    token_hash: str,
    expires_at: datetime,
    user_agent: str | None,
    ip_address: str | None,
) -> Row:
    row = fetch_one(
        """
        INSERT INTO refresh_tokens (user_id, token_hash, expires_at, user_agent, ip_address)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, issued_at, expires_at
        """,
        (user_id, token_hash, expires_at, (user_agent or None), ip_address),
    )
    assert row is not None
    return row


def find_active_refresh_token(token_hash: str) -> Row | None:
    return fetch_one(
        """
        SELECT rt.id, rt.user_id, rt.expires_at, rt.revoked_at, rt.replaced_by,
               u.email, u.display_name, u.is_active
        FROM refresh_tokens rt
        JOIN users u ON u.id = rt.user_id
        WHERE rt.token_hash = %s
        """,
        (token_hash,),
    )


def rotate_refresh_token(
    *,
    old_token_hash: str,
    user_id: str,
    new_token_hash: str,
    expires_at: datetime,
    user_agent: str | None,
    ip_address: str | None,
) -> Row | None:
    """Atomically revoke the presented token and issue its successor.

    Returns ``None`` when the old token was already revoked or expired, which
    is how token replay is detected.
    """
    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id
                    FROM refresh_tokens
                    WHERE token_hash = %s
                      AND user_id = %s
                      AND revoked_at IS NULL
                      AND expires_at > now()
                    FOR UPDATE
                    """,
                    (old_token_hash, user_id),
                )
                current = cur.fetchone()
                if current is None:
                    return None

                cur.execute(
                    """
                    INSERT INTO refresh_tokens (user_id, token_hash, expires_at, user_agent, ip_address)
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id, issued_at, expires_at
                    """,
                    (user_id, new_token_hash, expires_at, (user_agent or None), ip_address),
                )
                created = cur.fetchone()

                cur.execute(
                    """
                    UPDATE refresh_tokens
                    SET revoked_at = now(), replaced_by = %s
                    WHERE id = %s
                    """,
                    (created["id"], current["id"]),
                )
                return created


def revoke_refresh_token(token_hash: str) -> int:
    return execute(
        """
        UPDATE refresh_tokens
        SET revoked_at = now()
        WHERE token_hash = %s AND revoked_at IS NULL
        """,
        (token_hash,),
    )


def revoke_all_refresh_tokens(user_id: str) -> int:
    return execute(
        """
        UPDATE refresh_tokens
        SET revoked_at = now()
        WHERE user_id = %s AND revoked_at IS NULL
        """,
        (user_id,),
    )


def list_sessions(user_id: str) -> list[Row]:
    return fetch_all(
        """
        SELECT id, issued_at, expires_at, user_agent, token_hash
        FROM refresh_tokens
        WHERE user_id = %s AND revoked_at IS NULL AND expires_at > now()
        ORDER BY issued_at DESC
        LIMIT 100
        """,
        (user_id,),
    )


def purge_expired_refresh_tokens(older_than_days: int = 30) -> int:
    return execute(
        """
        DELETE FROM refresh_tokens
        WHERE expires_at < now() - make_interval(days => %s)
        """,
        (older_than_days,),
    )
