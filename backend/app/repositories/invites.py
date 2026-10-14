"""Invite code persistence for list sharing."""

from __future__ import annotations

from datetime import datetime, timedelta

import psycopg

from app.core.security import generate_invite_code, utcnow
from app.db.pool import Row, connection, execute, fetch_all, fetch_one, fetch_value

MAX_CODE_ATTEMPTS = 5


def create(
    *,
    list_id: str,
    created_by: str,
    mode: str,
    role: str,
    expires_in_hours: int | None,
    max_uses: int | None,
) -> Row:
    expires_at = utcnow() + timedelta(hours=expires_in_hours) if expires_in_hours else None

    # Retry on the astronomically unlikely code collision instead of failing.
    last_error: Exception | None = None
    for _ in range(MAX_CODE_ATTEMPTS):
        code = generate_invite_code()
        try:
            row = fetch_one(
                """
                INSERT INTO shopping_list_invites (
                    shopping_list_id, code, mode, role, created_by, expires_at, max_uses
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id, shopping_list_id AS list_id, code, mode, role,
                          expires_at, max_uses, uses, revoked, created_at
                """,
                (list_id, code, mode, role, created_by, expires_at, max_uses),
            )
            assert row is not None
            return row
        except psycopg.errors.UniqueViolation as exc:  # pragma: no cover - rare
            last_error = exc
            continue

    raise RuntimeError("Не удалось сгенерировать уникальный код приглашения") from last_error


def get_by_code(code: str) -> Row | None:
    return fetch_one(
        """
        SELECT i.id, i.shopping_list_id AS list_id, i.code, i.mode, i.role,
               i.expires_at, i.max_uses, i.uses, i.revoked, i.created_at,
               sl.name AS list_name,
               sl.user_id AS owner_id,
               owner.display_name AS owner_name,
               (SELECT count(*) FROM shopping_list_items
                 WHERE shopping_list_id = sl.id) AS item_count,
               (SELECT count(*) FROM shopping_list_members
                 WHERE shopping_list_id = sl.id) AS member_count
        FROM shopping_list_invites i
        JOIN shopping_lists sl ON sl.id = i.shopping_list_id
        JOIN users owner ON owner.id = sl.user_id
        WHERE i.code = %s
        """,
        (code,),
    )


def list_for_list(list_id: str, *, include_revoked: bool = False) -> list[Row]:
    condition = "" if include_revoked else " AND revoked = false"
    return fetch_all(
        f"""
        SELECT id, shopping_list_id AS list_id, code, mode, role,
               expires_at, max_uses, uses, revoked, created_at
        FROM shopping_list_invites
        WHERE shopping_list_id = %s{condition}
        ORDER BY created_at DESC
        LIMIT 100
        """,
        (list_id,),
    )


def count_active(list_id: str) -> int:
    return int(
        fetch_value(
            """
            SELECT count(*)
            FROM shopping_list_invites
            WHERE shopping_list_id = %s
              AND revoked = false
              AND (expires_at IS NULL OR expires_at > now())
              AND (max_uses IS NULL OR uses < max_uses)
            """,
            (list_id,),
        )
        or 0
    )


def consume(code: str) -> Row | None:
    """Atomically validate and increment an invite's use counter.

    Returns ``None`` if the code is unknown, revoked, expired or exhausted, so
    the check and the increment cannot race.
    """
    return fetch_one(
        """
        UPDATE shopping_list_invites
        SET uses = uses + 1
        WHERE code = %s
          AND revoked = false
          AND (expires_at IS NULL OR expires_at > now())
          AND (max_uses IS NULL OR uses < max_uses)
        RETURNING id, shopping_list_id AS list_id, mode, role, uses, max_uses
        """,
        (code,),
    )


def revoke(list_id: str, code: str) -> bool:
    return (
        execute(
            """
            UPDATE shopping_list_invites
            SET revoked = true
            WHERE shopping_list_id = %s AND code = %s AND revoked = false
            """,
            (list_id, code),
        )
        > 0
    )


def revoke_all(list_id: str) -> int:
    return execute(
        """
        UPDATE shopping_list_invites
        SET revoked = true
        WHERE shopping_list_id = %s AND revoked = false
        """,
        (list_id,),
    )


def find_reusable(
    *, list_id: str, mode: str, role: str
) -> Row | None:
    """An existing open-ended invite, so repeated share clicks reuse one code."""
    return fetch_one(
        """
        SELECT id, shopping_list_id AS list_id, code, mode, role,
               expires_at, max_uses, uses, revoked, created_at
        FROM shopping_list_invites
        WHERE shopping_list_id = %s
          AND mode = %s
          AND role = %s
          AND revoked = false
          AND expires_at IS NULL
          AND max_uses IS NULL
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (list_id, mode, role),
    )
