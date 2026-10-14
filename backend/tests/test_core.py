"""Unit tests for normalization, security primitives and the rate limiter."""

from __future__ import annotations

import pytest

from app.core.normalization import (
    basket_key,
    clean_display_name,
    head_noun,
    normalize_item_name,
)
from app.core.rate_limit import RateLimiter
from app.core.security import (
    decode_access_token,
    create_access_token,
    generate_invite_code,
    hash_password,
    hash_refresh_token,
    needs_rehash,
    verify_password,
)


# --------------------------------------------------------- normalization


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2 л Молока 3.2%", "молока"),
        ("  ХЛЕБ   Бородинский  ", "хлеб бородинский"),
        ("Картошка 5кг", "картошка"),
        ("яйца x10", "яйца"),
        ("Сыр Гауда 200 г", "сыр гауда"),
        ("МАСЛО!!! сливочное", "масло сливочное"),
        ("купить хлеб срочно", "хлеб"),
        ("ЁЛКА", "елка"),
        ("Молоко 3,2 %", "молоко"),
        ("колбаса   докторская", "колбаса докторская"),
    ],
)
def test_normalize_item_name(raw: str, expected: str) -> None:
    assert normalize_item_name(raw) == expected


def test_normalize_never_returns_none_for_unit_only_input() -> None:
    # "2 л" is entirely units; the key must still be a string, not empty crash.
    assert isinstance(normalize_item_name("2 л"), str)


def test_head_noun() -> None:
    assert head_noun("молоко простоквашино 3.2%") == "молоко"
    assert head_noun("") == ""


def test_basket_key_is_order_independent_and_deduplicated() -> None:
    assert basket_key(["Хлеб", "молоко 3.2%", "ХЛЕБ", "  "]) == basket_key(
        ["молоко", "хлеб"]
    )


def test_clean_display_name_collapses_whitespace() -> None:
    assert clean_display_name("  Мой\tсписок\n\n покупок ") == "Мой список покупок"


def test_clean_display_name_strips_control_characters() -> None:
    assert "\x00" not in clean_display_name("с\x00нулём")


def test_clean_display_name_caps_length() -> None:
    assert len(clean_display_name("a" * 500)) == 300


# ------------------------------------------------------------- passwords


def test_password_roundtrip() -> None:
    stored = hash_password("StrongPass123")
    assert verify_password("StrongPass123", stored)
    assert not verify_password("StrongPass124", stored)


def test_hash_is_salted() -> None:
    assert hash_password("same") != hash_password("same")


def test_verify_password_handles_garbage() -> None:
    for stored in (None, "", "not-a-hash", "pbkdf2_sha256$abc$def$ghi"):
        assert verify_password("StrongPass123", stored) is False


def test_low_iteration_hash_is_rejected() -> None:
    """A hash weakened to an unsafe cost must not authenticate."""
    weak = hash_password("StrongPass123", iterations=310_000)
    tampered = weak.replace("$310000$", "$1000$", 1)
    assert verify_password("StrongPass123", tampered) is False


def test_needs_rehash_detects_outdated_cost() -> None:
    from app.config import settings

    current = hash_password("x")
    assert needs_rehash(current) is False

    # A hash created with fewer rounds than we now require must be upgraded.
    outdated = hash_password("x", iterations=310_000)
    expected = settings.PBKDF2_ITERATIONS > 310_000
    assert needs_rehash(outdated) is expected

    assert needs_rehash(None) is True
    assert needs_rehash("md5$whatever") is True


# ---------------------------------------------------------------- tokens


def test_access_token_roundtrip() -> None:
    token, expires_at = create_access_token(
        user_id="11111111-1111-1111-1111-111111111111",
        display_name="Тест",
        email="t@example.com",
    )
    payload = decode_access_token(token)
    assert payload["sub"] == "11111111-1111-1111-1111-111111111111"
    assert payload["type"] == "access"
    assert expires_at is not None


def test_tampered_token_rejected() -> None:
    from app.core.errors import InvalidTokenError

    token, _ = create_access_token(user_id="x", display_name="n", email="e@x.ru")
    head, body, signature = token.split(".")
    with pytest.raises(InvalidTokenError):
        decode_access_token(f"{head}.{body}.{signature[:-2]}xx")


def test_expired_token_rejected() -> None:
    from app.core.errors import TokenExpiredError

    token, _ = create_access_token(
        user_id="x", display_name="n", email="e@x.ru", expires_minutes=-1
    )
    with pytest.raises(TokenExpiredError):
        decode_access_token(token)


def test_refresh_token_hash_is_stable_and_opaque() -> None:
    token = "some-refresh-token-value"
    assert hash_refresh_token(token) == hash_refresh_token(token)
    assert token not in hash_refresh_token(token)
    assert len(hash_refresh_token(token)) == 64


def test_invite_code_avoids_confusable_characters() -> None:
    for _ in range(200):
        code = generate_invite_code()
        assert len(code) == 12
        assert not set(code) & set("IO01")


def test_invite_codes_are_unique() -> None:
    codes = {generate_invite_code() for _ in range(1000)}
    assert len(codes) == 1000


# ----------------------------------------------------------- rate limiter


async def test_rate_limiter_allows_then_blocks() -> None:
    limiter = RateLimiter(limit=3, window=60)
    assert [await limiter.allow("ip") for _ in range(3)] == [True, True, True]

    allowed, retry_after = await limiter.check("ip")
    assert allowed is False
    assert retry_after > 0


async def test_rate_limiter_is_per_key() -> None:
    limiter = RateLimiter(limit=1, window=60)
    assert await limiter.allow("a") is True
    assert await limiter.allow("b") is True
    assert await limiter.allow("a") is False


async def test_rate_limiter_window_expires() -> None:
    limiter = RateLimiter(limit=1, window=1)
    assert await limiter.allow("ip") is True
    assert await limiter.allow("ip") is False

    import asyncio

    await asyncio.sleep(1.1)
    assert await limiter.allow("ip") is True


def test_rate_limiter_rejects_bad_configuration() -> None:
    with pytest.raises(ValueError):
        RateLimiter(limit=0, window=60)
    with pytest.raises(ValueError):
        RateLimiter(limit=10, window=0)
