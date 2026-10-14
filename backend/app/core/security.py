"""Password hashing and JWT handling.

Passwords use PBKDF2-HMAC-SHA256 with a per-password salt and the iteration
count embedded in the stored string, so the cost can be raised over time
without invalidating existing passwords (see :func:`needs_rehash`).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import jwt

from app.config import settings
from app.core.errors import InvalidTokenError, TokenExpiredError

PBKDF2_PREFIX: Final = "pbkdf2_sha256"
PBKDF2_SALT_BYTES: Final = 16
PBKDF2_MIN_ITERATIONS: Final = 100_000
HASH_DIGEST: Final = "sha256"

TOKEN_TYPE_ACCESS: Final = "access"
TOKEN_TYPE_REFRESH: Final = "refresh"

# A dummy hash with the current cost, used to keep login timing uniform for
# unknown emails (otherwise response time leaks whether an account exists).
_DUMMY_PASSWORD: Final = "smartsupply-timing-equalizer"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------- passwords


def hash_password(password: str, *, iterations: int | None = None) -> str:
    if not password:
        raise ValueError("Password cannot be empty")

    rounds = iterations or settings.PBKDF2_ITERATIONS
    salt = secrets.token_bytes(PBKDF2_SALT_BYTES)
    digest = hashlib.pbkdf2_hmac(HASH_DIGEST, password.encode("utf-8"), salt, rounds)

    return (
        f"{PBKDF2_PREFIX}${rounds}$"
        f"{base64.b64encode(salt).decode('ascii')}$"
        f"{base64.b64encode(digest).decode('ascii')}"
    )


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        algo, rounds_text, salt_b64, hash_b64 = stored_hash.split("$", 3)
        if algo != PBKDF2_PREFIX:
            return False

        rounds = int(rounds_text)
        if rounds < PBKDF2_MIN_ITERATIONS:
            return False

        salt = base64.b64decode(salt_b64.encode("ascii"), validate=True)
        expected = base64.b64decode(hash_b64.encode("ascii"), validate=True)
        candidate = hashlib.pbkdf2_hmac(HASH_DIGEST, password.encode("utf-8"), salt, rounds)
        return hmac.compare_digest(candidate, expected)
    except (ValueError, TypeError, UnicodeError):
        return False


def needs_rehash(stored_hash: str | None) -> bool:
    """True when a stored hash uses fewer rounds than we now require."""
    if not stored_hash:
        return True
    try:
        algo, rounds_text, _, _ = stored_hash.split("$", 3)
        return algo != PBKDF2_PREFIX or int(rounds_text) < settings.PBKDF2_ITERATIONS
    except (ValueError, TypeError):
        return True


def waste_password_time() -> None:
    """Spend roughly one hash worth of CPU to equalize login timing."""
    hashlib.pbkdf2_hmac(
        HASH_DIGEST,
        _DUMMY_PASSWORD.encode("utf-8"),
        b"\x00" * PBKDF2_SALT_BYTES,
        settings.PBKDF2_ITERATIONS,
    )


# ------------------------------------------------------------------- tokens


def create_access_token(
    *,
    user_id: str,
    display_name: str,
    email: str,
    expires_minutes: int | None = None,
) -> tuple[str, datetime]:
    now = utcnow()
    expires_at = now + timedelta(minutes=expires_minutes or settings.JWT_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "name": display_name,
        "email": email,
        "type": TOKEN_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "jti": secrets.token_urlsafe(8),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, expires_at


def decode_access_token(token: str) -> dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenExpiredError() from exc
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError) as exc:
        raise InvalidTokenError() from exc

    if payload.get("type") not in (None, TOKEN_TYPE_ACCESS):
        # A refresh token must never be accepted as an access token.
        raise InvalidTokenError("Ожидался access-токен")

    subject = str(payload.get("sub") or "")
    if not subject:
        raise InvalidTokenError()

    return payload


def generate_refresh_token() -> str:
    """An opaque, high-entropy string; only its hash is ever stored."""
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def refresh_token_expiry() -> datetime:
    return utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)


# ------------------------------------------------------------ invite codes


INVITE_ALPHABET: Final = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no I, O, 0, 1


def generate_invite_code(length: int = 12) -> str:
    """Human-transcribable code with ~60 bits of entropy at length 12."""
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(length))
