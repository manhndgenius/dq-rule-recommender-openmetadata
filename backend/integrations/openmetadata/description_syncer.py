"""Service để sync descriptions từ schema file lên OpenMetadata.

Usage:
    python -m backend.integrations.openmetadata.description_syncer

Hoặc import trong code:
    from backend.integrations.openmetadata.description_syncer import DescriptionSyncer
    syncer = DescriptionSyncer()
    syncer.run()
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

import requests

# Thêm backend vào path để import được settings
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from backend.config.settings import settings

logger = logging.getLogger(__name__)


class DescriptionSyncer:
    """Sync descriptions từ local schema JSON file lên OpenMetadata."""

    def __init__(
        self,
        schema_file: str | Path | None = None,
        server_url: str | None = None,
        token: str | None = None,
    ):
        """Khởi tạo DescriptionSyncer.

        Args:
            schema_file: Đường dẫn file schema JSON. Mặc định: doc/healthcare_schema.json
            server_url: OpenMetadata server URL. Đọc từ env nếu không truyền.
            token: OpenMetadata JWT token. Đọc từ env nếu không truyền.
        """
        # Resolve schema file path
        if schema_file is None:
            self._schema_file = Path(__file__).resolve().parents[3] / "doc" / "healthcare_schema_vi.json"
        else:
            self._schema_file = Path(schema_file)

        # OpenMetadata config từ settings
        self._server_url = server_url or settings.openmetadata_base_url
        self._token = token or settings.openmetadata_jwt_token

        self._session = requests.Session()
        self._session.headers.update({
            "Content-Type": "application/json-patch+json",
            "Accept": "application/json",
        })
        if self._token:
            self._session.headers["Authorization"] = f"Bearer {self._token}"

        self._schema_data: dict[str, Any] | None = None
        self._stats = {
            "tables_updated": 0,
            "tables_skipped": 0,
            "columns_updated": 0,
            "columns_skipped": 0,
            "errors": 0,
        }

    def _load_schema(self) -> dict[str, Any]:
        """Load schema file JSON."""
        if self._schema_data is not None:
            return self._schema_data

        if not self._schema_file.exists():
            raise FileNotFoundError(f"Schema file not found: {self._schema_file}")

        with open(self._schema_file, "r", encoding="utf-8") as f:
            self._schema_data = json.load(f)

        logger.info(f"Loaded schema from {self._schema_file}")
        return self._schema_data

    def _get_table_fqn(self, table_name: str) -> str:
        """Build fully qualified name cho table.

        Format: service.database.schema.table
        Ví dụ: healthcare_postgres.HealthCare.public.patients
        """
        return f"healthcare_postgres.HealthCare.public.{table_name}"

    def _patch_description(self, endpoint: str, patch_data: dict[str, Any]) -> bool:
        """Gửi PATCH request lên OpenMetadata.

        Args:
            endpoint: API endpoint (ví dụ: /tables/name/...)
            patch_data: Data để patch. Sẽ được wrap thành JSON Patch format:
                [{"op": "replace", "path": "/description", "value": "..."}]

        Returns:
            True nếu thành công, False nếu thất bại.
        """
        url = f"{self._server_url}{endpoint}"

        # OpenMetadata yêu cầu JSON Patch format
        # https://datatracker.ietf.org/doc/html/rfc6902
        description = patch_data.get("description", "")
        json_patch = [
            {"op": "replace", "path": "/description", "value": description}
        ]

        try:
            resp = self._session.patch(url, json=json_patch, timeout=30)
            if resp.status_code in (200, 201):
                return True
            elif resp.status_code == 404:
                logger.warning(f"Not found: {url}")
                return False
            else:
                logger.error(f"PATCH {url} failed: {resp.status_code} - {resp.text[:200]}")
                self._stats["errors"] += 1
                return False
        except Exception as e:
            logger.error(f"PATCH {url} exception: {e}")
            self._stats["errors"] += 1
            return False

    def _update_table_description(self, table: dict[str, Any]) -> bool:
        """Update description cho một table.

        Args:
            table: Table data từ schema JSON.

        Returns:
            True nếu thành công.
        """
        table_name = table.get("name")
        description = table.get("description", "")

        if not description:
            logger.info(f"Skipping table '{table_name}' - no description")
            self._stats["tables_skipped"] += 1
            return False

        fqn = self._get_table_fqn(table_name)
        endpoint = f"/tables/name/{fqn}"

        # _patch_description sẽ wrap thành JSON Patch format
        patch_data = {
            "description": description,
        }

        logger.info(f"Updating table '{table_name}' description...")
        success = self._patch_description(endpoint, patch_data)

        if success:
            self._stats["tables_updated"] += 1
            logger.info(f"✓ Updated table '{table_name}'")
        else:
            self._stats["tables_skipped"] += 1

        return success

    def _update_column_description(
        self,
        table_name: str,
        column: dict[str, Any],
        column_index: int,
    ) -> bool:
        """Update description cho một column.

        Args:
            table_name: Tên table cha.
            column: Column data từ schema JSON.

        Returns:
            True nếu thành công.
        """
        column_name = column.get("name")
        description = column.get("description", "")

        if not description:
            self._stats["columns_skipped"] += 1
            return False

        table_fqn = self._get_table_fqn(table_name)

        # OpenMetadata column description update dùng endpoint khác
        # Format: /tables/{id}/columns/{name}/description
        # Hoặc dùng JSON Patch cho column description
        url = f"{self._server_url}/tables/name/{table_fqn}"

        # Dùng JSON Patch format
        json_patch = [
            {"op": "replace", "path": f"/columns/{column_index}/description", "value": description}
        ]

        try:
            resp = self._session.patch(url, json=json_patch, timeout=30)
            if resp.status_code in (200, 201):
                self._stats["columns_updated"] += 1
                logger.info(f"  ✓ Updated column '{column_name}'")
                return True
            elif resp.status_code == 404:
                logger.warning(f"  Column not found: {table_fqn}.{column_name}")
                self._stats["columns_skipped"] += 1
                return False
            else:
                logger.error(f"  PATCH column failed: {resp.status_code} - {resp.text[:100]}")
                self._stats["errors"] += 1
                return False
        except Exception as e:
            logger.error(f"  PATCH column exception: {e}")
            self._stats["errors"] += 1
            return False

    def sync_tables(self, dry_run: bool = False) -> dict[str, int]:
        """Sync table descriptions lên OpenMetadata.

        Args:
            dry_run: Nếu True, chỉ hiển thị những gì sẽ update mà không thực hiện.

        Returns:
            Statistics dict.
        """
        schema_data = self._load_schema()
        tables = schema_data.get("tables", [])

        logger.info(f"Found {len(tables)} tables in schema")

        for table in tables:
            table_name = table.get("name", "unknown")

            if dry_run:
                desc = table.get("description", "")
                logger.info(f"[DRY RUN] Would update table '{table_name}': {desc[:50]}...")
                self._stats["tables_updated"] += 1
                continue

            self._update_table_description(table)

        return self._stats

    def sync_columns(self, dry_run: bool = False) -> dict[str, int]:
        """Sync column descriptions lên OpenMetadata.

        Args:
            dry_run: Nếu True, chỉ hiển thị những gì sẽ update mà không thực hiện.

        Returns:
            Statistics dict.
        """
        schema_data = self._load_schema()
        tables = schema_data.get("tables", [])

        logger.info(f"Syncing columns for {len(tables)} tables...")

        for table in tables:
            table_name = table.get("name", "unknown")
            columns = table.get("columns", [])

            logger.info(f"Table '{table_name}': {len(columns)} columns")

            for idx, column in enumerate(columns):
                column_name = column.get("name", "unknown")

                if dry_run:
                    desc = column.get("description", "")
                    logger.info(f"  [DRY RUN] Would update '{column_name}': {desc[:50]}...")
                    self._stats["columns_updated"] += 1
                    continue

                self._update_column_description(table_name, column, idx)

        return self._stats

    def sync_all(self, dry_run: bool = False) -> dict[str, int]:
        """Sync tất cả descriptions (tables + columns).

        Args:
            dry_run: Nếu True, chỉ hiển thị những gì sẽ update.

        Returns:
            Statistics dict.
        """
        logger.info("=" * 60)
        logger.info("Starting description sync to OpenMetadata")
        logger.info(f"Server URL: {self._server_url}")
        logger.info(f"Schema file: {self._schema_file}")
        logger.info(f"Dry run: {dry_run}")
        logger.info("=" * 60)

        # Sync tables
        logger.info("\n--- Syncing Tables ---")
        self.sync_tables(dry_run=dry_run)

        # Sync columns
        logger.info("\n--- Syncing Columns ---")
        self.sync_columns(dry_run=dry_run)

        # Summary
        logger.info("\n" + "=" * 60)
        logger.info("Sync Complete!")
        logger.info(f"  Tables updated: {self._stats['tables_updated']}")
        logger.info(f"  Tables skipped: {self._stats['tables_skipped']}")
        logger.info(f"  Columns updated: {self._stats['columns_updated']}")
        logger.info(f"  Columns skipped: {self._stats['columns_skipped']}")
        logger.info(f"  Errors: {self._stats['errors']}")
        logger.info("=" * 60)

        return self._stats

    def check_connection(self) -> bool:
        """Kiểm tra kết nối tới OpenMetadata.

        Returns:
            True nếu kết nối thành công.
        """
        try:
            resp = self._session.get(
                f"{self._server_url}/system/version",
                timeout=10
            )
            if resp.status_code == 200:
                logger.info(f"✓ Connected to OpenMetadata: {resp.text[:100]}")
                return True
            else:
                logger.error(f"✗ Connection failed: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"✗ Connection error: {e}")
            return False


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Sync descriptions from schema JSON to OpenMetadata"
    )
    parser.add_argument(
        "--schema",
        type=str,
        default=None,
        help="Path to schema JSON file (default: doc/healthcare_schema.json)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )
    parser.add_argument(
        "--tables-only",
        action="store_true",
        help="Only sync table descriptions",
    )
    parser.add_argument(
        "--columns-only",
        action="store_true",
        help="Only sync column descriptions",
    )
    parser.add_argument(
        "--check-connection",
        action="store_true",
        help="Only check connection to OpenMetadata",
    )

    args = parser.parse_args()

    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    # Create syncer
    syncer = DescriptionSyncer(schema_file=args.schema)

    # Check connection
    if args.check_connection:
        success = syncer.check_connection()
        sys.exit(0 if success else 1)

    # Sync
    if args.tables_only:
        syncer.sync_tables(dry_run=args.dry_run)
    elif args.columns_only:
        syncer.sync_columns(dry_run=args.dry_run)
    else:
        syncer.sync_all(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
