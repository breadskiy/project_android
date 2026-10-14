"""Minimal forward-only SQL migration runner.

Why not Alembic: it pulls in SQLAlchemy, which this project does not use.
Migrations here are plain ``.sql`` files named ``NNN_description.sql`` and are
applied in numeric order inside a transaction, tracked in
``schema_migrations``. An advisory lock makes concurrent startups safe.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from app.config import settings
from app.core.logging import get_logger
from app.db.pool import connection

logger = get_logger("smartsupply.migrations")

MIGRATION_NAME_RE = re.compile(r"^(\d{3,4})_([a-z0-9_]+)\.sql$")
ADVISORY_LOCK_KEY = 0x5A11_57  # arbitrary but stable

CREATE_TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS public.schema_migrations (
    version     integer PRIMARY KEY,
    name        text NOT NULL,
    checksum    text NOT NULL,
    applied_at  timestamptz NOT NULL DEFAULT now()
)
"""


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    path: Path

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


def discover(directory: Path | None = None) -> list[Migration]:
    directory = directory or settings.migrations_dir
    if not directory.is_dir():
        return []

    found: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        match = MIGRATION_NAME_RE.match(path.name)
        if not match:
            logger.warning("Skipping migration with unexpected name: %s", path.name)
            continue
        found.append(Migration(version=int(match.group(1)), name=match.group(2), path=path))

    versions = [m.version for m in found]
    duplicates = {v for v in versions if versions.count(v) > 1}
    if duplicates:
        raise RuntimeError(f"Duplicate migration versions: {sorted(duplicates)}")

    return sorted(found, key=lambda m: m.version)


def applied_versions() -> dict[int, str]:
    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TRACKING_TABLE)
            cur.execute("SELECT version, checksum FROM public.schema_migrations")
            return {row["version"]: row["checksum"] for row in cur.fetchall()}


def run_migrations(directory: Path | None = None) -> list[int]:
    """Apply pending migrations; return the versions that were applied."""
    migrations = discover(directory)
    if not migrations:
        logger.info("No migration files found")
        return []

    already = applied_versions()
    applied: list[int] = []

    with connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
        try:
            # Refresh inside the lock: another process may have applied some.
            with conn.cursor() as cur:
                cur.execute(CREATE_TRACKING_TABLE)
                cur.execute("SELECT version, checksum FROM public.schema_migrations")
                already = {row["version"]: row["checksum"] for row in cur.fetchall()}

            for migration in migrations:
                known_checksum = already.get(migration.version)
                if known_checksum is not None:
                    if known_checksum != migration.checksum:
                        logger.warning(
                            "Migration %03d_%s changed after being applied "
                            "(stored checksum differs); not re-running it.",
                            migration.version,
                            migration.name,
                        )
                    continue

                logger.info("Applying migration %03d_%s", migration.version, migration.name)
                with conn.transaction():
                    with conn.cursor() as cur:
                        cur.execute(migration.sql)
                        cur.execute(
                            """
                            INSERT INTO public.schema_migrations (version, name, checksum)
                            VALUES (%s, %s, %s)
                            """,
                            (migration.version, migration.name, migration.checksum),
                        )
                applied.append(migration.version)
        finally:
            with conn.cursor() as cur:
                cur.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))

    if applied:
        logger.info("Applied %d migration(s): %s", len(applied), applied)
    else:
        logger.info("Database schema is up to date (%d migrations known)", len(migrations))
    return applied


def migration_status(directory: Path | None = None) -> list[dict[str, object]]:
    migrations = discover(directory)
    already = applied_versions()
    return [
        {
            "version": m.version,
            "name": m.name,
            "applied": m.version in already,
            "checksum_match": already.get(m.version) in (None, m.checksum),
        }
        for m in migrations
    ]
