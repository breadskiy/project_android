"""Authentication, session and settings tests."""

from __future__ import annotations

import httpx
import pytest


async def test_health_reports_database(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


async def test_register_returns_user_without_password(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/auth/register",
        json={
            "email": "Newbie@Example.COM",
            "password": "StrongPass123",
            "display_name": "  Новичок  ",
        },
    )
    assert response.status_code == 201
    user = response.json()["user"]
    # Email normalized, name trimmed, no secret material echoed back.
    assert user["email"] == "newbie@example.com"
    assert user["display_name"] == "Новичок"
    assert "password" not in response.text
    assert "hash" not in response.text


async def test_register_rejects_duplicate_email_case_insensitively(
    client: httpx.AsyncClient,
) -> None:
    payload = {
        "email": "dup@example.com",
        "password": "StrongPass123",
        "display_name": "Первый",
    }
    assert (await client.post("/auth/register", json=payload)).status_code == 201

    response = await client.post(
        "/auth/register",
        json={**payload, "email": "DUP@example.com", "display_name": "Второй"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "user_already_exists"


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "not-an-email", "password": "StrongPass123", "display_name": "X"},
        {"email": "a@b.ru", "password": "short", "display_name": "X"},
        {"email": "a@b.ru", "password": "StrongPass123", "display_name": ""},
        {"email": "a@b.ru", "password": "StrongPass123"},
        {
            "email": "a@b.ru",
            "password": "StrongPass123",
            "display_name": "X",
            "is_admin": True,
        },
    ],
)
async def test_register_validation(client: httpx.AsyncClient, payload: dict) -> None:
    response = await client.post("/auth/register", json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


async def test_login_issues_both_tokens(client: httpx.AsyncClient, user) -> None:
    response = await client.post(
        "/auth/login", json={"email": user.email, "password": user.password}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"] and body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert body["expires_in"] > 0


async def test_login_rejects_wrong_password(client: httpx.AsyncClient, user) -> None:
    response = await client.post(
        "/auth/login", json={"email": user.email, "password": "WrongPass123"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_login_unknown_email_gives_same_error(client: httpx.AsyncClient) -> None:
    """Unknown account and wrong password must be indistinguishable."""
    response = await client.post(
        "/auth/login", json={"email": "ghost@example.com", "password": "StrongPass123"}
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"


async def test_protected_endpoint_requires_token(client: httpx.AsyncClient) -> None:
    response = await client.get("/lists")
    assert response.status_code == 401
    assert response.headers.get("www-authenticate") == "Bearer"


@pytest.mark.parametrize(
    "header",
    [
        "Bearer garbage.token.value",
        "Bearer ",
        "Basic dXNlcjpwYXNz",
        "eyJhbGciOiJIUzI1NiJ9.e30.signature",
    ],
)
async def test_invalid_authorization_headers(client: httpx.AsyncClient, header: str) -> None:
    response = await client.get("/lists", headers={"Authorization": header})
    assert response.status_code == 401


async def test_refresh_token_cannot_be_used_as_access_token(
    client: httpx.AsyncClient, user
) -> None:
    response = await client.get(
        "/lists", headers={"Authorization": f"Bearer {user.refresh_token}"}
    )
    assert response.status_code == 401


async def test_refresh_rotates_tokens(client: httpx.AsyncClient, user) -> None:
    response = await client.post("/auth/refresh", json={"refresh_token": user.refresh_token})
    assert response.status_code == 200
    body = response.json()
    assert body["refresh_token"] != user.refresh_token

    # The new access token works.
    me = await client.get("/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


async def test_refresh_replay_revokes_all_sessions(client: httpx.AsyncClient, user) -> None:
    """Reusing a rotated refresh token is treated as a leak."""
    first = await client.post("/auth/refresh", json={"refresh_token": user.refresh_token})
    assert first.status_code == 200
    new_refresh = first.json()["refresh_token"]

    replay = await client.post("/auth/refresh", json={"refresh_token": user.refresh_token})
    assert replay.status_code == 401

    # The legitimate successor is revoked too, forcing a fresh login.
    after = await client.post("/auth/refresh", json={"refresh_token": new_refresh})
    assert after.status_code == 401


async def test_logout_revokes_refresh_token(client: httpx.AsyncClient, user) -> None:
    response = await client.post(
        "/auth/logout", headers=user.headers, json={"refresh_token": user.refresh_token}
    )
    assert response.status_code == 200

    reuse = await client.post("/auth/refresh", json={"refresh_token": user.refresh_token})
    assert reuse.status_code == 401


async def test_logout_all_sessions(client: httpx.AsyncClient, user) -> None:
    await user.login()
    second_refresh = user.refresh_token

    response = await client.post(
        "/auth/logout", headers=user.headers, json={"all_sessions": True}
    )
    assert response.status_code == 200
    assert (
        await client.post("/auth/refresh", json={"refresh_token": second_refresh})
    ).status_code == 401


async def test_sessions_listing(client: httpx.AsyncClient, user) -> None:
    await user.login()
    response = await client.get("/auth/sessions", headers=user.headers)
    assert response.status_code == 200
    assert len(response.json()["items"]) >= 2


async def test_change_password_and_revoke_sessions(client: httpx.AsyncClient, user) -> None:
    old_refresh = user.refresh_token
    response = await client.post(
        "/auth/change-password",
        headers=user.headers,
        json={"current_password": user.password, "new_password": "EvenStronger456"},
    )
    assert response.status_code == 200

    assert (
        await client.post("/auth/refresh", json={"refresh_token": old_refresh})
    ).status_code == 401
    assert (
        await client.post(
            "/auth/login", json={"email": user.email, "password": "EvenStronger456"}
        )
    ).status_code == 200
    assert (
        await client.post("/auth/login", json={"email": user.email, "password": user.password})
    ).status_code == 401


async def test_change_password_requires_current(client: httpx.AsyncClient, user) -> None:
    response = await client.post(
        "/auth/change-password",
        headers=user.headers,
        json={"current_password": "NotMyPassword1", "new_password": "EvenStronger456"},
    )
    assert response.status_code == 401


async def test_me_returns_profile_and_stats(client: httpx.AsyncClient, user) -> None:
    response = await client.get("/me", headers=user.headers)
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == user.email
    assert body["settings"]["ai_suggestions_enabled"] is True
    assert set(body["stats"]) == {"lists_owned", "lists_shared", "items_total"}


async def test_disabled_account_loses_access_immediately(
    client: httpx.AsyncClient, user
) -> None:
    """A valid JWT must not outlive the account it belongs to."""
    from app.db.pool import execute

    execute("UPDATE users SET is_active = false WHERE id = %s", (user.user_id,))

    response = await client.get("/me", headers=user.headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "user_disabled"


async def test_security_headers_present(client: httpx.AsyncClient) -> None:
    response = await client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["cache-control"] == "no-store"


async def test_oversized_body_rejected(client: httpx.AsyncClient) -> None:
    huge = "x" * (2 * 1024 * 1024)
    response = await client.post(
        "/auth/register",
        json={"email": "a@b.ru", "password": "StrongPass123", "display_name": huge},
    )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "payload_too_large"
