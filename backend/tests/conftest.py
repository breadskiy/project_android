"""Shared pytest fixtures.

Tests run against a dedicated database (``<DB_NAME>_test`` by default) that is
recreated from ``database/database.sql`` plus the migrations, so the working
application database is never touched.
"""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Must be set before app.config is imported anywhere.
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("RUN_MIGRATIONS_ON_STARTUP", "false")
os.environ.setdefault("RATE_LIMIT_REQUESTS", "100000")
os.environ.setdefault("AUTH_RATE_LIMIT_REQUESTS", "100000")
# Детерминированная статистика в тестах, независимо от локального .env.
os.environ["SUGGESTIONS_PROVIDER"] = "statistical"
# Keep hashing cheap so the suite is not dominated by PBKDF2.
os.environ.setdefault("PBKDF2_ITERATIONS", "310000")
# Pool chatter drowns out assertion output otherwise.
os.environ.setdefault("LOG_LEVEL", "WARNING")

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.config import settings  # noqa: E402

TEST_DB_NAME = os.getenv("TEST_DB_NAME") or f"{settings.DB_NAME}_test"
settings.DB_NAME = TEST_DB_NAME  # type: ignore[misc]

from app.db import pool as pool_module  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: longer-running test")


@pytest.fixture(scope="session", autouse=True)
def database() -> Iterator[None]:
    """Recreate the test database once per session."""
    from scripts.bootstrap_db import (
        apply_base_schema,
        create_database,
        database_exists,
        drop_database,
    )

    if database_exists(TEST_DB_NAME):
        drop_database(TEST_DB_NAME)
    create_database(TEST_DB_NAME)
    apply_base_schema(TEST_DB_NAME)

    pool_module.init_pool()
    try:
        from app.db.migrator import run_migrations

        run_migrations()
        yield
    finally:
        pool_module.close_pool()


@pytest.fixture(scope="session")
def seeded(database: None) -> None:
    """Catalog and curated pair rules, needed by suggestion tests."""
    from scripts.seed_catalog import seed_catalog, seed_pair_rules

    seed_catalog()
    seed_pair_rules()


@pytest.fixture(autouse=True)
def clean_tables(database: None) -> Iterator[None]:
    """Remove per-test data, keeping seeded catalog rows intact."""
    yield
    pool_module.execute("DELETE FROM users")
    pool_module.execute("DELETE FROM suggestion_cache")
    pool_module.execute("DELETE FROM events")
    pool_module.execute(
        "UPDATE product_pair_rules SET accepted_count = 0, rejected_count = 0"
    )
    pool_module.execute("DELETE FROM product_pair_rules WHERE source = 'statistical'")
    pool_module.execute("DELETE FROM product_pair_rules WHERE source = 'llm'")


@pytest.fixture
async def client(database: None) -> AsyncIterator[httpx.AsyncClient]:
    """HTTP client speaking to the app over ASGI (no network, no server)."""
    transport = httpx.ASGITransport(app=fastapi_app)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://testserver",
        timeout=30.0,
    ) as async_client:
        yield async_client


class UserSession:
    """A registered, logged-in user plus its auth headers."""

    def __init__(self, client: httpx.AsyncClient, email: str, password: str) -> None:
        self._client = client
        self.email = email
        self.password = password
        self.user_id: str = ""
        self.access_token: str = ""
        self.refresh_token: str = ""

    @property
    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def register_and_login(self, display_name: str) -> "UserSession":
        response = await self._client.post(
            "/auth/register",
            json={
                "email": self.email,
                "password": self.password,
                "display_name": display_name,
            },
        )
        assert response.status_code == 201, response.text
        self.user_id = response.json()["user"]["id"]
        await self.login()
        return self

    async def login(self) -> None:
        response = await self._client.post(
            "/auth/login", json={"email": self.email, "password": self.password}
        )
        assert response.status_code == 200, response.text
        body = response.json()
        self.access_token = body["access_token"]
        self.refresh_token = body["refresh_token"]


@pytest.fixture
async def user_factory(client: httpx.AsyncClient):
    counter = {"n": 0}

    async def make(display_name: str = "Тестовый пользователь") -> UserSession:
        counter["n"] += 1
        import uuid

        email = f"test_{counter['n']}_{uuid.uuid4().hex[:8]}@example.com"
        session = UserSession(client, email, "StrongPass123")
        return await session.register_and_login(display_name)

    return make


@pytest.fixture
async def user(user_factory) -> UserSession:
    return await user_factory("Первый пользователь")


@pytest.fixture
async def other_user(user_factory) -> UserSession:
    return await user_factory("Второй пользователь")


@pytest.fixture
async def shopping_list(client: httpx.AsyncClient, user: UserSession) -> dict:
    response = await client.post(
        "/lists",
        headers=user.headers,
        json={"name": "Продукты", "items": ["хлеб", "молоко"]},
    )
    assert response.status_code == 201, response.text
    return response.json()
