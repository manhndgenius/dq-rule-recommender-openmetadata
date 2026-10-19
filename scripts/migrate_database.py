"""Apply or inspect PostgreSQL schema migrations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Support direct execution from the repository root:
# `python scripts/migrate_database.py`.
ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.storage.db_service import db_service
from backend.storage.migration_runner import MigrationRunner


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero when unapplied migrations exist.",
    )
    args = parser.parse_args()
    runner = MigrationRunner(db_service)

    if args.check:
        pending = runner.pending()
        if pending:
            print("Pending migrations: " + ", ".join(pending))
            return 1
        print("Database schema is up to date.")
        return 0

    applied = runner.apply()
    if applied:
        print("Applied migrations: " + ", ".join(applied))
    else:
        print("Database schema is already up to date.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

