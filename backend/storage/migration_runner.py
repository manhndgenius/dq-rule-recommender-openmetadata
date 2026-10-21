"""Versioned PostgreSQL migration runner for application persistence."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from backend.storage.db_service import DatabaseService


MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"
MIGRATION_TABLE = "dq_schema_migrations"


class MigrationRunner:
    def __init__(
        self,
        database: DatabaseService,
        migrations_dir: Path = MIGRATIONS_DIR,
    ) -> None:
        self.database = database
        self.migrations_dir = migrations_dir

    def migration_files(self) -> Iterable[Path]:
        return sorted(self.migrations_dir.glob("[0-9][0-9][0-9]_*.sql"))

    def apply(self) -> list[str]:
        applied: list[str] = []
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS dq_schema_migrations (
                        version VARCHAR(255) PRIMARY KEY,
                        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                    )
                    """
                )
                cursor.execute(f"SELECT version FROM {MIGRATION_TABLE}")
                completed = {row[0] for row in cursor.fetchall()}

                for migration in self.migration_files():
                    version = migration.name
                    if version in completed:
                        continue
                    cursor.execute(migration.read_text(encoding="utf-8"))
                    cursor.execute(
                        f"INSERT INTO {MIGRATION_TABLE}(version) VALUES (%s)",
                        (version,),
                    )
                    applied.append(version)
        return applied

    def pending(self) -> list[str]:
        files = [migration.name for migration in self.migration_files()]
        with self.database.connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT to_regclass(%s)",
                    (f"public.{MIGRATION_TABLE}",),
                )
                if cursor.fetchone()[0] is None:
                    return files
                cursor.execute(f"SELECT version FROM {MIGRATION_TABLE}")
                completed = {row[0] for row in cursor.fetchall()}
        return [version for version in files if version not in completed]

