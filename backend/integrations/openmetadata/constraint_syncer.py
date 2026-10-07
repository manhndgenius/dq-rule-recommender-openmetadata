"""Synchronize PostgreSQL PK, UNIQUE and FK constraints to OpenMetadata."""

from __future__ import annotations

import logging
import os
from typing import Any

import psycopg2
import requests

from backend.config.settings import settings

logger = logging.getLogger(__name__)
MANAGED_TYPES = {"PRIMARY_KEY", "UNIQUE", "FOREIGN_KEY"}


class ConstraintSyncer:
    """Publish database constraints while preserving OpenMetadata-only types."""

    def __init__(
        self,
        pg_host: str | None = None,
        pg_port: int | None = None,
        pg_db: str | None = None,
        pg_user: str | None = None,
        pg_password: str | None = None,
        pg_schema: str | None = None,
        table_fqn_prefix: str | None = None,
        server_url: str | None = None,
        token: str | None = None,
    ) -> None:
        self._pg_conn = psycopg2.connect(
            host=pg_host or os.getenv("PGHOST", "localhost"),
            port=pg_port or int(os.getenv("PGPORT", "5432")),
            dbname=pg_db or os.getenv("PGDATABASE", "HealthCare"),
            user=pg_user or os.getenv("PGUSER", "postgres"),
            password=pg_password or os.getenv("PGPASSWORD", "postgres"),
        )
        self._pg_schema = pg_schema or os.getenv("PGSCHEMA", "public")
        self._fqn_prefix = (
            table_fqn_prefix
            or os.getenv("FQN", "healthcare_postgres.HealthCare.public")
        ).rstrip(".")
        self._server_url = (server_url or settings.openmetadata_base_url).rstrip("/")
        self._session = requests.Session()
        self._session.headers.update(
            {
                "Accept": "application/json",
            }
        )
        auth_token = token if token is not None else settings.openmetadata_jwt_token
        if auth_token:
            self._session.headers["Authorization"] = f"Bearer {auth_token}"
        self.stats = {
            "tables_changed": 0,
            "tables_unchanged": 0,
            "constraints_synced": 0,
            "errors": 0,
        }

    def get_database_constraints(self) -> dict[str, dict[str, list[dict[str, Any]]]]:
        """Read constraints without the duplicate rows produced by information_schema joins."""
        with self._pg_conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT source_table.relname, constraint_record.conname,
                       constraint_record.contype,
                       ARRAY(
                           SELECT source_column.attname
                           FROM unnest(constraint_record.conkey)
                                WITH ORDINALITY AS source_key(attnum, position)
                           JOIN pg_attribute source_column
                             ON source_column.attrelid = constraint_record.conrelid
                            AND source_column.attnum = source_key.attnum
                           ORDER BY source_key.position
                       ),
                       target_table.relname,
                       CASE WHEN constraint_record.contype = 'f' THEN ARRAY(
                           SELECT target_column.attname
                           FROM unnest(constraint_record.confkey)
                                WITH ORDINALITY AS target_key(attnum, position)
                           JOIN pg_attribute target_column
                             ON target_column.attrelid = constraint_record.confrelid
                            AND target_column.attnum = target_key.attnum
                           ORDER BY target_key.position
                       ) ELSE NULL END
                FROM pg_constraint constraint_record
                JOIN pg_class source_table
                  ON source_table.oid = constraint_record.conrelid
                JOIN pg_namespace source_schema
                  ON source_schema.oid = source_table.relnamespace
                LEFT JOIN pg_class target_table
                  ON target_table.oid = constraint_record.confrelid
                WHERE source_schema.nspname = %s
                  AND constraint_record.contype IN ('p', 'u', 'f')
                ORDER BY source_table.relname, constraint_record.contype,
                         constraint_record.conname
                """,
                (self._pg_schema,),
            )
            rows = cursor.fetchall()

        result: dict[str, dict[str, list[dict[str, Any]]]] = {}
        for table, name, kind, columns, target_table, target_columns in rows:
            groups = result.setdefault(
                table, {"primary_keys": [], "unique": [], "foreign_keys": []}
            )
            item: dict[str, Any] = {"name": name, "columns": list(columns)}
            if kind == "p":
                groups["primary_keys"].append(item)
            elif kind == "u":
                groups["unique"].append(item)
            else:
                item.update(
                    {
                        "target_table": target_table,
                        "target_columns": list(target_columns),
                    }
                )
                groups["foreign_keys"].append(item)
        return result

    def _get_openmetadata_table(self, table_name: str) -> dict[str, Any] | None:
        url = (
            f"{self._server_url}/tables/name/{self._fqn_prefix}.{table_name}"
            "?fields=tableConstraints"
        )
        try:
            response = self._session.get(url, timeout=30)
            if response.ok:
                return response.json()
            logger.error("GET %s failed: %s %s", table_name, response.status_code, response.text[:200])
        except requests.RequestException as exc:
            logger.error("GET %s failed: %s", table_name, exc)
        self.stats["errors"] += 1
        return None

    def _as_openmetadata(
        self, database_constraints: dict[str, list[dict[str, Any]]]
    ) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        result.extend(
            {"constraintType": "PRIMARY_KEY", "columns": item["columns"]}
            for item in database_constraints["primary_keys"]
        )
        result.extend(
            {"constraintType": "UNIQUE", "columns": item["columns"]}
            for item in database_constraints["unique"]
        )
        result.extend(
            {
                "constraintType": "FOREIGN_KEY",
                "columns": item["columns"],
                "referredColumns": [
                    f"{self._fqn_prefix}.{item['target_table']}.{column}"
                    for column in item["target_columns"]
                ],
                "relationshipType": "MANY_TO_ONE",
            }
            for item in database_constraints["foreign_keys"]
        )
        return result

    @staticmethod
    def _key(item: dict[str, Any]) -> tuple[Any, ...]:
        return (
            item.get("constraintType"),
            tuple(item.get("columns") or []),
            tuple(str(value) for value in item.get("referredColumns") or []),
            item.get("relationshipType"),
        )

    def _desired(
        self,
        current: list[dict[str, Any]],
        database_constraints: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        preserved = [
            item for item in current if item.get("constraintType") not in MANAGED_TYPES
        ]
        return preserved + self._as_openmetadata(database_constraints)

    def _same(self, left: list[dict[str, Any]], right: list[dict[str, Any]]) -> bool:
        return {self._key(item) for item in left} == {self._key(item) for item in right}

    def _patch(
        self, table_name: str, table: dict[str, Any], desired: list[dict[str, Any]]
    ) -> bool:
        patches: list[dict[str, Any]] = [
            {"op": "add", "path": "/tableConstraints", "value": desired}
        ]
        primary_columns = {
            column.casefold()
            for item in desired
            if item.get("constraintType") == "PRIMARY_KEY"
            for column in item.get("columns", [])
        }
        for index, column in enumerate(table.get("columns") or []):
            if (
                column.get("name", "").casefold() in primary_columns
                and column.get("constraint") != "PRIMARY_KEY"
            ):
                patches.append(
                    {
                        "op": "add",
                        "path": f"/columns/{index}/constraint",
                        "value": "PRIMARY_KEY",
                    }
                )

        url = f"{self._server_url}/tables/name/{self._fqn_prefix}.{table_name}"
        try:
            response = self._session.patch(
                url,
                json=patches,
                headers={"Content-Type": "application/json-patch+json"},
                timeout=30,
            )
            if response.ok:
                return True
            logger.error(
                "PATCH %s failed: %s %s",
                table_name,
                response.status_code,
                response.text[:300],
            )
        except requests.RequestException as exc:
            logger.error("PATCH %s failed: %s", table_name, exc)
        self.stats["errors"] += 1
        return False

    def sync(self, dry_run: bool = False) -> dict[str, int]:
        """Compute and optionally apply all table constraint changes."""
        for table_name, database_constraints in self.get_database_constraints().items():
            table = self._get_openmetadata_table(table_name)
            if table is None:
                continue
            current = table.get("tableConstraints") or []
            desired = self._desired(current, database_constraints)
            if self._same(current, desired):
                self.stats["tables_unchanged"] += 1
                logger.info("[UNCHANGED] %s", table_name)
                continue

            managed = self._as_openmetadata(database_constraints)
            logger.info(
                "[%s] %s: %s",
                "DRY-RUN" if dry_run else "SYNC",
                table_name,
                managed,
            )
            if dry_run or self._patch(table_name, table, desired):
                self.stats["tables_changed"] += 1
                self.stats["constraints_synced"] += len(managed)

        logger.info("Tables changed: %s", self.stats["tables_changed"])
        logger.info("Tables unchanged: %s", self.stats["tables_unchanged"])
        logger.info("Constraints synced: %s", self.stats["constraints_synced"])
        logger.info("Errors: %s", self.stats["errors"])
        return dict(self.stats)

    def close(self) -> None:
        self._pg_conn.close()
        self._session.close()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync PostgreSQL PK, UNIQUE and FK constraints to OpenMetadata"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    syncer = ConstraintSyncer()
    try:
        stats = syncer.sync(dry_run=args.dry_run)
        return 1 if stats["errors"] else 0
    finally:
        syncer.close()


if __name__ == "__main__":
    raise SystemExit(main())
