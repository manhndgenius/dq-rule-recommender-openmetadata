"""Sync FK/PK constraints từ PostgreSQL lên OpenMetadata qua API.

Usage:
    python -m backend.integrations.openmetadata.relationship_syncer

Lưu ý:
    - Column constraints (PRIMARY_KEY) có thể update qua PATCH API
    - FK relationships cần dùng OpenMetadata Ingestion connector hoặc UI
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any

import psycopg2
import requests

# Thêm backend vào path để import được settings
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class RelationshipSyncer:
    """Sync FK/PK constraints từ PostgreSQL lên OpenMetadata."""

    def __init__(
        self,
        pg_host: str = "localhost",
        pg_port: int = 5432,
        pg_db: str = "HealthCare",
        pg_user: str = "postgres",
        pg_password: str = "postgres",
        server_url: str | None = None,
        token: str | None = None,
    ):
        """Khởi tạo RelationshipSyncer."""
        # PostgreSQL connection
        self._pg_conn = psycopg2.connect(
            host=pg_host,
            port=pg_port,
            dbname=pg_db,
            user=pg_user,
            password=pg_password,
        )
        self._pg_conn.autocommit = True

        # OpenMetadata config
        self._server_url = server_url or settings.openmetadata_base_url
        self._token = token or settings.openmetadata_jwt_token

        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json-patch+json",
            "Accept": "application/json",
        })
        if self._token:
            self._session.headers["Authorization"] = f"Bearer {self._token}"

        self._stats = {
            "pk_constraints_synced": 0,
            "fk_constraints_synced": 0,
            "errors": 0,
        }

    def _get_constraints(self) -> dict[str, Any]:
        """Lấy tất cả PK/FK constraints từ PostgreSQL."""
        cur = self._pg_conn.cursor()

        cur.execute("""
            SELECT
                tc.table_name,
                tc.constraint_name,
                tc.constraint_type,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            LEFT JOIN information_schema.constraint_column_usage ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.table_schema = 'public'
              AND tc.constraint_type IN ('PRIMARY KEY', 'FOREIGN KEY')
            ORDER BY tc.table_name, tc.constraint_type, tc.constraint_name
        """)

        constraints = {}
        for row in cur.fetchall():
            table, con_name, con_type, col, foreign_table, foreign_col = row

            if table not in constraints:
                constraints[table] = {"primary_keys": [], "foreign_keys": []}

            if con_type == "PRIMARY KEY":
                constraints[table]["primary_keys"].append({
                    "column": col,
                    "constraint_name": con_name,
                })
            elif con_type == "FOREIGN KEY":
                constraints[table]["foreign_keys"].append({
                    "column": col,
                    "constraint_name": con_name,
                    "foreign_table": foreign_table,
                    "foreign_column": foreign_col,
                })

        cur.close()
        return constraints

    def _get_table_columns(self, table_name: str) -> list[dict]:
        """Lấy danh sách columns của table từ OpenMetadata."""
        url = f"{self._server_url}/tables/name/healthcare_postgres.HealthCare.public.{table_name}"
        try:
            # GET request - dùng header riêng
            headers = {
                "Accept": "application/json",
                "Authorization": f"Bearer {self._token}"
            }
            resp = requests.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.json().get("columns", [])
        except Exception as e:
            logger.error(f"Error getting columns for {table_name}: {e}")
        return []

    def _get_table_fqn(self, table_name: str) -> str:
        """Build fully qualified name."""
        return f"healthcare_postgres.HealthCare.public.{table_name}"

    def _sync_column_constraints(self, table_name: str, constraints: dict[str, Any]) -> int:
        """Sync column constraints (PRIMARY_KEY) lên OpenMetadata.

        Args:
            table_name: Tên table
            constraints: Dict chứa PKs và FKs

        Returns:
            Số lượng constraints đã sync
        """
        pk_columns = [pk["column"].lower() for pk in constraints.get("primary_keys", [])]

        if not pk_columns:
            return 0

        # Lấy columns từ OpenMetadata
        columns = self._get_table_columns(table_name)

        # Build patches để update constraints
        patches = []
        for idx, col in enumerate(columns):
            col_name = col.get("name", "").lower()
            if col_name in pk_columns:
                patches.append({
                    "op": "replace",
                    "path": f"/columns/{idx}/constraint",
                    "value": "PRIMARY_KEY"
                })

        if not patches:
            return 0

        # Gửi PATCH request
        url = f"{self._server_url}/tables/name/{self._get_table_fqn(table_name)}"
        try:
            resp = self._session.patch(url, json=patches, timeout=30)
            if resp.status_code in (200, 201):
                logger.info(f"[OK] Synced PK constraints for '{table_name}': {pk_columns}")
                return len(patches)
            else:
                logger.error(f"[ERROR] {table_name}: {resp.status_code} - {resp.text[:100]}")
                self._stats["errors"] += 1
                return 0
        except Exception as e:
            logger.error(f"[ERROR] {table_name}: {e}")
            self._stats["errors"] += 1
            return 0

    def sync_column_constraints(self, dry_run: bool = False) -> dict[str, int]:
        """Sync column constraints từ PostgreSQL lên OpenMetadata.

        Args:
            dry_run: Nếu True, chỉ hiển thị những gì sẽ sync

        Returns:
            Statistics dict
        """
        logger.info("=" * 60)
        logger.info("Syncing Column Constraints (PRIMARY_KEY)")
        logger.info("=" * 60)

        constraints = self._get_constraints()

        for table_name, table_constraints in constraints.items():
            pks = table_constraints.get("primary_keys", [])
            if not pks:
                continue

            pk_cols = [pk["column"] for pk in pks]
            logger.info(f"{table_name}: {pk_cols}")

            if dry_run:
                self._stats["pk_constraints_synced"] += len(pks)
                continue

            synced = self._sync_column_constraints(table_name, table_constraints)
            self._stats["pk_constraints_synced"] += synced

        logger.info("\n" + "=" * 60)
        logger.info("Column Constraints Sync Complete!")
        logger.info(f"  PK constraints synced: {self._stats['pk_constraints_synced']}")
        logger.info(f"  Errors: {self._stats['errors']}")
        logger.info("=" * 60)

        return self._stats

    def print_fk_summary(self):
        """In summary của FK relationships (không sync được qua API thường)."""
        logger.info("\n" + "=" * 60)
        logger.info("FK RELATIONSHIPS (for reference)")
        logger.info("=" * 60)

        constraints = self._get_constraints()

        for table_name, table_constraints in sorted(constraints.items()):
            fks = table_constraints.get("foreign_keys", [])
            if not fks:
                continue

            logger.info(f"\n{table_name}:")
            for fk in fks:
                logger.info(f"  {fk['column']} -> {fk['foreign_table']}.{fk['foreign_column']}")

        logger.info("\n" + "=" * 60)
        logger.info("NOTE: FK relationships need OpenMetadata Ingestion Connector")
        logger.info("or manual entry via OpenMetadata UI.")
        logger.info("=" * 60)

    def check_connection(self) -> bool:
        """Kiểm tra kết nối."""
        try:
            resp = self._session.get(
                f"{self._server_url}/system/version",
                timeout=10
            )
            return resp.status_code == 200
        except Exception:
            return False

    def close(self):
        """Đóng kết nối PostgreSQL."""
        if self._pg_conn:
            self._pg_conn.close()


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync FK/PK constraints from PostgreSQL to OpenMetadata"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be synced without making changes",
    )
    parser.add_argument(
        "--check-connection",
        action="store_true",
        help="Only check connections",
    )
    parser.add_argument(
        "--fk-only",
        action="store_true",
        help="Only show FK summary (no API update)",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    syncer = RelationshipSyncer()

    if args.check_connection:
        if syncer.check_connection():
            print("[OK] Connections OK")
        else:
            print("[ERROR] Connection failed")
        syncer.close()
        return

    if args.fk_only:
        syncer.print_fk_summary()
        syncer.close()
        return

    syncer.sync_column_constraints(dry_run=args.dry_run)
    syncer.print_fk_summary()
    syncer.close()


if __name__ == "__main__":
    main()
