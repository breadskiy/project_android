from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Any, Iterator
from uuid import uuid4

import jwt
import psycopg2
from psycopg2 import errors
from psycopg2.extras import Json
from psycopg2.pool import ThreadedConnectionPool

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


if load_dotenv is not None:
    load_dotenv()

logger = logging.getLogger("smartsupply.db")


# -----------------------------------------------------------------------------
# Configuration
# -----------------------------------------------------------------------------

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", "5432"))
DB_NAME = os.getenv("DB_NAME", "smart_supply_lists")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))

DB_MIN_CONNECTIONS = max(1, int(os.getenv("DB_MIN_CONNECTIONS", "1")))
DB_MAX_CONNECTIONS = max(DB_MIN_CONNECTIONS, int(os.getenv("DB_MAX_CONNECTIONS", "10")))


if not DB_PASSWORD:
    raise RuntimeError(
        "DB_PASSWORD is not configured. Set it in the environment or .env file."
    )

if not JWT_SECRET_KEY:
    raise RuntimeError(
        "JWT_SECRET_KEY is not configured. Set it in the environment or .env file."
    )

if len(JWT_SECRET_KEY) < 32:
    raise RuntimeError("JWT_SECRET_KEY must contain at least 32 characters.")


# -----------------------------------------------------------------------------
# Connection pool
# -----------------------------------------------------------------------------

pool = ThreadedConnectionPool(
    minconn=DB_MIN_CONNECTIONS,
    maxconn=DB_MAX_CONNECTIONS,
    host=DB_HOST,
    port=DB_PORT,
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    connect_timeout=5,
    application_name="smart_supply_api",
)


@contextmanager
def db_connection() -> Iterator[Any]:
    """
    Get one connection from the pool.

    Every operation either commits successfully or rolls back before the
    connection is returned to the pool.
    """
    conn = pool.getconn()
    try:
        conn.set_client_encoding("UTF8")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


@contextmanager
def db_cursor() -> Iterator[Any]:
    """Get a cursor with automatic commit/rollback handling."""
    with db_connection() as conn:
        with conn.cursor() as cursor:
            yield cursor


# -----------------------------------------------------------------------------
# Password hashing
# -----------------------------------------------------------------------------

PBKDF2_PREFIX = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 310_000
PBKDF2_SALT_BYTES = 16


def hash_password(password: str) -> str:
    if not password:
        raise ValueError("Password cannot be empty")

    salt = os.urandom(PBKDF2_SALT_BYTES)
    hashed = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return (
        f"{PBKDF2_PREFIX}${PBKDF2_ITERATIONS}$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(hashed).decode('ascii')}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, iterations_text, salt_b64, hash_b64 = stored_hash.split("$", 3)
        if algo != PBKDF2_PREFIX:
            return False

        iterations = int(iterations_text)
        if iterations < 100_000:
            return False

        salt = base64.b64decode(salt_b64.encode("ascii"), validate=True)
        expected_hash = base64.b64decode(hash_b64.encode("ascii"), validate=True)

        test_hash = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            iterations,
        )
        return hmac.compare_digest(test_hash, expected_hash)
    except (ValueError, TypeError, UnicodeError):
        return False


# -----------------------------------------------------------------------------
# Authentication
# -----------------------------------------------------------------------------

def register_user(
    email: str,
    password: str,
    display_name: str,
    phone: str = "",
    locale: str = "ru-RU",
    timezone_value: str = "Europe/Moscow",
    profile: dict | None = None,
    preferred_store_id: str | None = None,
) -> dict[str, Any]:
    user_id = str(uuid4())
    now = datetime.now(timezone.utc)
    password_hash = hash_password(password)
    profile = profile or {}

    try:
        with db_cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM users WHERE email = %s LIMIT 1",
                (email,),
            )
            if cursor.fetchone() is not None:
                return {
                    "ok": False,
                    "message": "Пользователь с такой почтой уже существует",
                }

            cursor.execute(
                """
                INSERT INTO users (
                    id,
                    email,
                    password_hash,
                    display_name,
                    phone,
                    locale,
                    timezone,
                    profile,
                    preferred_store_id,
                    is_active,
                    email_verified,
                    created_at,
                    last_login
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    user_id,
                    email,
                    password_hash,
                    display_name,
                    phone,
                    locale,
                    timezone_value,
                    Json(profile),
                    preferred_store_id,
                    True,
                    False,
                    now,
                    now,
                ),
            )

        return {
            "ok": True,
            "message": "Регистрация успешна",
            "user": {
                "id": user_id,
                "email": email,
                "display_name": display_name,
            },
        }

    except errors.UniqueViolation:
        # Handles the race where another request creates the same email
        # between SELECT and INSERT.
        return {
            "ok": False,
            "message": "Пользователь с такой почтой уже существует",
        }


def login_user(email: str, password: str) -> dict[str, Any]:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, password_hash, display_name, email, is_active
            FROM users
            WHERE email = %s
            LIMIT 1
            """,
            (email,),
        )
        row = cursor.fetchone()

        if row is None:
            return {"ok": False, "message": "Неверные учетные данные"}

        user_id, password_hash, display_name, stored_email, is_active = row

        if not is_active:
            return {"ok": False, "message": "Пользователь отключен"}

        if not verify_password(password, password_hash):
            return {"ok": False, "message": "Неверные учетные данные"}

        now = datetime.now(timezone.utc)
        cursor.execute(
            "UPDATE users SET last_login = %s WHERE id = %s",
            (now, user_id),
        )

    expire_time = now + timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "name": str(display_name),
        "email": str(stored_email),
        "iat": now,
        "exp": expire_time,
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)

    return {
        "ok": True,
        "message": "Авторизация успешна",
        "token": token,
    }


def verify_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )

        return {
            "ok": True,
            "user_id": str(payload["sub"]),
            "display_name": str(payload.get("name", "")),
            "email": str(payload.get("email", "")),
        }

    except jwt.ExpiredSignatureError:
        return {
            "ok": False,
            "message": "Время сессии истекло. Авторизуйтесь заново.",
        }
    except (jwt.InvalidTokenError, KeyError, TypeError):
        return {
            "ok": False,
            "message": "Недействительный или поврежденный токен.",
        }


# -----------------------------------------------------------------------------
# Shopping lists
# -----------------------------------------------------------------------------

def create_shopping_list(user_id: str, name: str, items: list[str]) -> dict[str, Any]:
    list_id = str(uuid4())
    now = datetime.now(timezone.utc)

    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO shopping_lists (
                id, user_id, name, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (list_id, user_id, name, now, now),
        )

        for raw_item_name in items:
            item_name = raw_item_name.strip()
            if not item_name:
                continue

            cursor.execute(
                """
                INSERT INTO shopping_list_items (
                    id, shopping_list_id, name, quantity, added_at
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (str(uuid4()), list_id, item_name, 1, now),
            )

    return {
        "ok": True,
        "id": list_id,
        "name": name,
        "message": "Список успешно создан",
    }


def get_shopping_lists(user_id: str):
    query = """
        SELECT
            sl.id,
            sl.name,
            COUNT(sli.id),
            sl.is_shared,
            ARRAY(
                SELECT u.display_name
                FROM users u
                WHERE u.id = sl.user_id
                   OR (
                       sl.sharing_settings IS NOT NULL
                       AND sl.sharing_settings ? u.id::text
                   )
            ) AS members,
            (SELECT display_name FROM users WHERE id = sl.user_id) AS owner_name,
            sl.user_id
        FROM shopping_lists sl
        LEFT JOIN shopping_list_items sli
            ON sl.id = sli.shopping_list_id
        WHERE sl.user_id = %s
           OR (
               sl.is_shared = true
               AND sl.sharing_settings ? %s
           )
        GROUP BY
            sl.id,
            sl.name,
            sl.is_shared,
            sl.user_id,
            sl.sharing_settings,
            sl.created_at
        ORDER BY sl.created_at DESC
    """

    with db_cursor() as cursor:
        cursor.execute(query, (user_id, user_id))
        return cursor.fetchall()


def get_list_items(list_id: str):
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id, name
            FROM shopping_list_items
            WHERE shopping_list_id = %s
            ORDER BY added_at ASC
            """,
            (list_id,),
        )
        return cursor.fetchall()


def add_item_to_list(list_id: str, item_name: str) -> dict[str, Any]:
    item_id = str(uuid4())
    now = datetime.now(timezone.utc)

    with db_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO shopping_list_items (
                id, shopping_list_id, name, quantity, added_at
            )
            VALUES (%s, %s, %s, %s, %s)
            """,
            (item_id, list_id, item_name, 1, now),
        )

        cursor.execute(
            """
            UPDATE shopping_lists
            SET updated_at = %s
            WHERE id = %s
            """,
            (now, list_id),
        )

    return {"ok": True, "item_id": item_id}


def delete_item_from_list(item_id: str) -> bool:
    with db_cursor() as cursor:
        cursor.execute(
            "DELETE FROM shopping_list_items WHERE id = %s",
            (item_id,),
        )
    return True


def rename_shopping_list(list_id: str, new_name: str) -> tuple[bool, str]:
    with db_cursor() as cursor:
        cursor.execute(
            "SELECT description FROM shopping_lists WHERE id = %s",
            (list_id,),
        )
        row = cursor.fetchone()

        if row and row[0] == "system_favorite":
            return False, "Список «⭐ Избранное» нельзя переименовать."

        cursor.execute(
            """
            UPDATE shopping_lists
            SET name = %s, updated_at = %s
            WHERE id = %s
            """,
            (new_name, datetime.now(timezone.utc), list_id),
        )

        if cursor.rowcount == 0:
            return False, "Список не найден."

    return True, "Успешно"


def delete_shopping_list(user_id: str, list_id: str) -> tuple[bool, str]:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT user_id, description
            FROM shopping_lists
            WHERE id = %s
            """,
            (list_id,),
        )
        row = cursor.fetchone()

        if not row:
            return False, "Список не найден."

        owner_id = str(row[0])
        description = row[1]

        if description == "system_favorite" and owner_id == user_id:
            return False, "Системный список «⭐ Избранное» нельзя удалить."

        if owner_id == user_id:
            cursor.execute(
                "DELETE FROM shopping_list_items WHERE shopping_list_id = %s",
                (list_id,),
            )
            cursor.execute(
                "DELETE FROM shopping_lists WHERE id = %s",
                (list_id,),
            )
        else:
            cursor.execute(
                """
                UPDATE shopping_lists
                SET sharing_settings =
                    COALESCE(sharing_settings, '[]'::jsonb) - %s
                WHERE id = %s
                """,
                (user_id, list_id),
            )

    return True, "Список удален (или вы покинули общий список)."


def make_list_shared(list_id: str) -> bool:
    with db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE shopping_lists
            SET is_shared = true,
                sharing_settings = COALESCE(sharing_settings, '[]'::jsonb)
            WHERE id = %s
            """,
            (list_id,),
        )
        if cursor.rowcount == 0:
            return False
    return True


def join_shared_list(user_id: str, list_id: str) -> tuple[bool, str]:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT is_shared
            FROM shopping_lists
            WHERE id = %s
            """,
            (list_id,),
        )
        row = cursor.fetchone()

        if not row or not row[0]:
            return False, "Список не найден или не является общим."

        cursor.execute(
            """
            UPDATE shopping_lists
            SET sharing_settings = CASE
                WHEN COALESCE(sharing_settings, '[]'::jsonb) ? %s
                    THEN COALESCE(sharing_settings, '[]'::jsonb)
                ELSE
                    COALESCE(sharing_settings, '[]'::jsonb)
                    || jsonb_build_array(%s::text)
            END
            WHERE id = %s
            """,
            (user_id, user_id, list_id),
        )

    return True, "Вы успешно присоединились к общему списку."


def copy_list(user_id: str, list_id: str) -> tuple[bool, str]:
    with db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT name FROM shopping_lists WHERE id = %s",
                (list_id,),
            )
            row = cursor.fetchone()

            if not row:
                return False, "Оригинальный список не найден."

            original_name = str(row[0])

            cursor.execute(
                """
                SELECT name
                FROM shopping_list_items
                WHERE shopping_list_id = %s
                ORDER BY added_at ASC
                """,
                (list_id,),
            )
            item_names = [str(item[0]) for item in cursor.fetchall()]

            new_list_id = str(uuid4())
            now = datetime.now(timezone.utc)
            new_name = f"{original_name} (Копия)"

            cursor.execute(
                """
                INSERT INTO shopping_lists (
                    id, user_id, name, created_at, updated_at
                )
                VALUES (%s, %s, %s, %s, %s)
                """,
                (new_list_id, user_id, new_name, now, now),
            )

            for item_name in item_names:
                cursor.execute(
                    """
                    INSERT INTO shopping_list_items (
                        id, shopping_list_id, name, quantity, added_at
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (str(uuid4()), new_list_id, item_name, 1, now),
                )

    return True, "Копия списка успешно сохранена в ваши списки."


def rename_item(item_id: str, new_name: str) -> bool:
    with db_cursor() as cursor:
        cursor.execute(
            """
            UPDATE shopping_list_items
            SET name = %s
            WHERE id = %s
            """,
            (new_name, item_id),
        )

        if cursor.rowcount == 0:
            return False

        cursor.execute(
            """
            UPDATE shopping_lists
            SET updated_at = %s
            WHERE id = (
                SELECT shopping_list_id
                FROM shopping_list_items
                WHERE id = %s
            )
            """,
            (datetime.now(timezone.utc), item_id),
        )

    return True


def clear_list_items(list_id: str) -> bool:
    with db_cursor() as cursor:
        cursor.execute(
            """
            DELETE FROM shopping_list_items
            WHERE shopping_list_id = %s
            """,
            (list_id,),
        )

        cursor.execute(
            """
            UPDATE shopping_lists
            SET updated_at = %s
            WHERE id = %s
            """,
            (datetime.now(timezone.utc), list_id),
        )

        return cursor.rowcount > 0


def ensure_favorites_list(user_id: str) -> bool:
    with db_cursor() as cursor:
        cursor.execute(
            """
            SELECT id
            FROM shopping_lists
            WHERE user_id = %s
              AND description = 'system_favorite'
            LIMIT 1
            """,
            (user_id,),
        )

        if cursor.fetchone():
            return True

        now = datetime.now(timezone.utc)
        cursor.execute(
            """
            INSERT INTO shopping_lists (
                id, user_id, name, description, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (
                str(uuid4()),
                user_id,
                "⭐ Избранное",
                "system_favorite",
                now,
                now,
            ),
        )

    return True


def ping_database() -> bool:
    """Simple DB readiness check."""
    with db_cursor() as cursor:
        cursor.execute("SELECT 1")
        return cursor.fetchone() == (1,)


def close_pool() -> None:
    pool.closeall()
