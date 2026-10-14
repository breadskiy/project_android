"""PostgreSQL access layer built on psycopg 3.

Windows note
------------
psycopg 3 cannot run in async mode on ``ProactorEventLoop``, which is the
default loop uvicorn uses on Windows (``uvicorn.loops.asyncio`` returns
``ProactorEventLoop`` unless subprocesses are used). Forcing a
``SelectorEventLoop`` would cap the app at 512 sockets and the
``WindowsSelectorEventLoopPolicy`` helper is deprecated for removal in
Python 3.16.

So we use psycopg 3's *sync* pool and hand queries to a bounded worker thread
pool via ``asyncio.to_thread``-style offloading. The event loop is never
blocked, the code stays portable, and we still get psycopg 3's better type
handling, ``dict_row`` results and server-side parameter binding.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterator, Sequence
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Any, ParamSpec, TypeVar

import psycopg
from psycopg import Connection, sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from app.config import settings
from app.core.errors import ServiceUnavailableError
from app.core.logging import get_logger

logger = get_logger("smartsupply.db")

P = ParamSpec("P")
T = TypeVar("T")

Params = Sequence[Any] | dict[str, Any] | None
Row = dict[str, Any]

_pool: ConnectionPool | None = None
_executor: ThreadPoolExecutor | None = None


# ---------------------------------------------------------------- lifecycle


def build_conninfo() -> str:
    return psycopg.conninfo.make_conninfo(**settings.conninfo_kwargs())  # type: ignore[arg-type]


def init_pool() -> ConnectionPool:
    """Create and open the connection pool. Idempotent."""
    global _pool, _executor

    if _pool is not None:
        return _pool

    pool = ConnectionPool(
        conninfo=build_conninfo(),
        min_size=settings.DB_MIN_CONNECTIONS,
        max_size=settings.DB_MAX_CONNECTIONS,
        kwargs={"row_factory": dict_row, "autocommit": False},
        name="smartsupply",
        open=False,
        timeout=settings.DB_CONNECT_TIMEOUT,
        max_idle=300.0,
    )
    pool.open(wait=True, timeout=max(10.0, float(settings.DB_CONNECT_TIMEOUT) * 2))

    _pool = pool
    _executor = ThreadPoolExecutor(
        max_workers=settings.DB_THREAD_POOL_SIZE,
        thread_name_prefix="db",
    )
    logger.info(
        "Database pool ready (min=%s max=%s threads=%s)",
        settings.DB_MIN_CONNECTIONS,
        settings.DB_MAX_CONNECTIONS,
        settings.DB_THREAD_POOL_SIZE,
    )
    return pool


def close_pool() -> None:
    """Close the pool and the worker threads. Idempotent."""
    global _pool, _executor

    if _executor is not None:
        _executor.shutdown(wait=True, cancel_futures=False)
        _executor = None

    if _pool is not None:
        _pool.close()
        _pool = None
        logger.info("Database pool closed")


def get_pool() -> ConnectionPool:
    if _pool is None:
        raise ServiceUnavailableError("Пул соединений с базой данных не инициализирован")
    return _pool


# ------------------------------------------------------- sync query helpers


@contextmanager
def connection() -> Iterator[Connection]:
    """Borrow a connection; commit on success, roll back on error."""
    pool = get_pool()
    with pool.connection() as conn:
        # psycopg's pool already commits on clean exit and rolls back on error.
        yield conn


@contextmanager
def transaction() -> Iterator[psycopg.Cursor]:
    """Run a block of statements as one explicit transaction."""
    with connection() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                yield cur


def fetch_all(query: str | sql.Composed, params: Params = None) -> list[Row]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return list(cur.fetchall())


def fetch_one(query: str | sql.Composed, params: Params = None) -> Row | None:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.fetchone()


def fetch_value(query: str | sql.Composed, params: Params = None) -> Any:
    row = fetch_one(query, params)
    if not row:
        return None
    return next(iter(row.values()))


def execute(query: str | sql.Composed, params: Params = None) -> int:
    """Execute a statement and return the affected row count."""
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            return cur.rowcount


# ------------------------------------------------------------ async bridging


async def run_in_thread(func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
    """Run a blocking DB callable on the bounded DB thread pool."""
    executor = _executor
    if executor is None:
        raise ServiceUnavailableError("Пул соединений с базой данных не инициализирован")
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, lambda: func(*args, **kwargs))


async def afetch_all(query: str | sql.Composed, params: Params = None) -> list[Row]:
    return await run_in_thread(fetch_all, query, params)


async def afetch_one(query: str | sql.Composed, params: Params = None) -> Row | None:
    return await run_in_thread(fetch_one, query, params)


async def afetch_value(query: str | sql.Composed, params: Params = None) -> Any:
    return await run_in_thread(fetch_value, query, params)


async def aexecute(query: str | sql.Composed, params: Params = None) -> int:
    return await run_in_thread(execute, query, params)


# ------------------------------------------------------------------- health


def ping() -> bool:
    return fetch_value("SELECT 1") == 1


async def aping() -> bool:
    return await run_in_thread(ping)


def pool_stats() -> dict[str, Any]:
    if _pool is None:
        return {"status": "closed"}
    return dict(_pool.get_stats())
