"""Create (or recreate) a database and apply the base schema + migrations.

Used for the test database and for bootstrapping a fresh environment.
Never touches the configured application database unless explicitly named.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import psycopg  # noqa: E402
from psycopg import sql  # noqa: E402

from app.config import settings  # noqa: E402


def admin_conninfo() -> str:
    """Connect to the maintenance database, not the target one."""
    return psycopg.conninfo.make_conninfo(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname="postgres",
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        connect_timeout=settings.DB_CONNECT_TIMEOUT,
    )


def target_conninfo(dbname: str) -> str:
    return psycopg.conninfo.make_conninfo(
        host=settings.DB_HOST,
        port=settings.DB_PORT,
        dbname=dbname,
        user=settings.DB_USER,
        password=settings.DB_PASSWORD,
        connect_timeout=settings.DB_CONNECT_TIMEOUT,
    )


def database_exists(dbname: str) -> bool:
    with psycopg.connect(admin_conninfo(), autocommit=True) as conn:
        row = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone()
        return row is not None


def drop_database(dbname: str) -> None:
    with psycopg.connect(admin_conninfo(), autocommit=True) as conn:
        conn.execute(
            """
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = %s AND pid <> pg_backend_pid()
            """,
            (dbname,),
        )
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(sql.Identifier(dbname)))
    print(f"dropped database {dbname}")


def create_database(dbname: str) -> None:
    with psycopg.connect(admin_conninfo(), autocommit=True) as conn:
        conn.execute(
            sql.SQL("CREATE DATABASE {} ENCODING 'UTF8'").format(sql.Identifier(dbname))
        )
    print(f"created database {dbname}")


def apply_base_schema(dbname: str) -> None:
    schema_path = PROJECT_ROOT / "database" / "database.sql"
    if not schema_path.is_file():
        raise SystemExit(f"base schema not found: {schema_path}")

    body = schema_path.read_text(encoding="utf-8")
    with psycopg.connect(target_conninfo(dbname)) as conn:
        with conn.cursor() as cur:
            cur.execute(body)
        conn.commit()
    print(f"applied base schema from {schema_path.name}")


def apply_migrations(dbname: str) -> None:
    """Apply migrations against an explicit database name."""
    from app.db import pool as pool_module
    from app.db.migrator import run_migrations

    original = settings.DB_NAME
    try:
        settings.DB_NAME = dbname  # type: ignore[misc]
        pool_module.init_pool()
        applied = run_migrations()
        print(f"migrations applied: {applied or 'none pending'}")
    finally:
        pool_module.close_pool()
        settings.DB_NAME = original  # type: ignore[misc]


def main() -> int:
    parser = argparse.ArgumentParser(description="Bootstrap a Smart Supply database")
    parser.add_argument("--dbname", default=f"{settings.DB_NAME}_test")
    parser.add_argument("--recreate", action="store_true", help="drop the database first")
    parser.add_argument("--base-schema", action="store_true", help="apply database/database.sql")
    parser.add_argument("--migrations", action="store_true", help="apply migrations/*.sql")
    args = parser.parse_args()

    dbname = args.dbname

    if dbname == settings.DB_NAME and args.recreate:
        raise SystemExit(
            f"refusing to drop the configured application database {dbname!r}; "
            "pass a different --dbname"
        )

    if args.recreate:
        drop_database(dbname)

    if not database_exists(dbname):
        create_database(dbname)
    else:
        print(f"database {dbname} already exists")

    if args.base_schema:
        apply_base_schema(dbname)
    if args.migrations:
        apply_migrations(dbname)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
