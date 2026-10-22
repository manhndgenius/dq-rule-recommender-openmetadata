"""Database service để lưu trữ và quản lý DQ rules trong PostgreSQL."""
import os
import json
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

import psycopg2
from psycopg2.extras import RealDictCursor

from backend.config.settings import settings

logger = logging.getLogger("db_service")


class DatabaseService:
    """Service để quản lý DQ rules trong PostgreSQL."""

    def __init__(self):
        self._connection_params = {
            'host': getattr(settings, 'postgres_host', 'localhost'),
            'port': getattr(settings, 'postgres_port', 5432),
            'user': getattr(settings, 'postgres_user', 'postgres'),
            'password': getattr(settings, 'postgres_password', 'postgres'),
            'database': getattr(settings, 'postgres_db', 'dq_rules'),
            'sslmode': getattr(settings, 'postgres_sslmode', 'prefer'),
        }

    def _get_connection(self):
        """Get database connection."""
        db_url = getattr(settings, 'database_url', None) or os.getenv('DATABASE_URL')
        if db_url:
            return psycopg2.connect(
                db_url,
                connect_timeout=settings.postgres_connect_timeout,
            )
        return psycopg2.connect(
            **self._connection_params,
            connect_timeout=settings.postgres_connect_timeout,
        )

    def connection(self):
        """Public connection factory used by repositories and migrations."""
        return self._get_connection()

    def check_ready(self) -> None:
        """Raise when PostgreSQL cannot accept a trivial query."""
        with self.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1")
                cur.fetchone()

    def init_database(self):
        """Compatibility entry point; schema changes live in migrations."""
        from backend.storage.migration_runner import MigrationRunner

        return MigrationRunner(self).apply()

    def save_rules(self, table_name: str, engine: str, rules: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Lưu rules vào database.

        - Xóa tất cả rules của engine đó cho table trước khi lưu
        - Lưu rules mới

        Args:
            table_name: Tên bảng
            engine: 'BASIC' hoặc 'ADVANCED'
            rules: Danh sách rules

        Returns:
            Dict với số lượng đã lưu
        """
        if not rules:
            return {'saved': 0, 'deleted': 0}

        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    # Begin transaction
                    conn.autocommit = False

                    # Delete existing rules for this table + engine
                    cur.execute(
                        "DELETE FROM dq_rules WHERE table_name = %s AND engine = %s",
                        (table_name, engine)
                    )
                    deleted_count = cur.rowcount

                    # Insert new rules
                    for rule in rules:
                        self._insert_rule(cur, rule)

                    conn.commit()
                    logger.info(f"Saved {len(rules)} {engine} rules for table {table_name}")

                    return {'saved': len(rules), 'deleted': deleted_count}

        except Exception as e:
            logger.error(f"Failed to save rules: {e}")
            raise

    def _insert_rule(self, cursor, rule: Dict[str, Any]):
        """Insert a single rule into database."""
        rule_id = rule.get('id') or f"rule_{rule.get('rule_type', 'unknown')}"

        # Convert complex fields to JSON
        parameters = json.dumps(rule.get('parameters', {}))
        evidence = json.dumps(rule.get('evidence', {}))
        params = json.dumps(rule.get('params', {}))
        conditions = json.dumps(rule.get('conditions', []))
        edited_params = json.dumps(rule.get('edited_parameters')) if rule.get('edited_parameters') else None

        # Convert target_columns list to array format
        target_columns = rule.get('target_columns', []) or rule.get('columns', [])

        cursor.execute("""
            INSERT INTO dq_rules (
                rule_id, table_name, rule_type, description, target_columns,
                parameters, expression, engine, confidence, reason, evidence,
                validation_status, validation_message, status, sql, violation_predicate,
                params, conditions, edited_parameters
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            rule_id,
            rule.get('table_name', 'unknown'),
            rule.get('rule_type'),
            rule.get('description'),
            target_columns,
            parameters,
            rule.get('expression'),
            rule.get('engine', 'BASIC'),
            rule.get('confidence', 1.0),
            rule.get('reason'),
            evidence,
            rule.get('validation_status', 'VALID'),
            rule.get('validation_message'),
            rule.get('status', 'DRAFT'),
            rule.get('sql'),
            rule.get('violation_predicate'),
            params,
            conditions,
            edited_params
        ))

    def get_rules(self, table_name: str, engine: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lấy rules từ database.

        Args:
            table_name: Tên bảng
            engine: 'BASIC', 'ADVANCED', hoặc None (lấy cả 2)

        Returns:
            Danh sách rules
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if engine:
                        cur.execute(
                            "SELECT * FROM dq_rules WHERE table_name = %s AND engine = %s ORDER BY id",
                            (table_name, engine)
                        )
                    else:
                        cur.execute(
                            "SELECT * FROM dq_rules WHERE table_name = %s ORDER BY id",
                            (table_name,)
                        )

                    rows = cur.fetchall()
                    rules = []
                    for row in rows:
                        rule = dict(row)
                        # Convert PostgreSQL arrays back to Python lists
                        if rule.get('target_columns') and isinstance(rule['target_columns'], str):
                            rule['target_columns'] = rule['target_columns']
                        # Convert JSONB fields back from string if needed
                        for field in ['parameters', 'evidence', 'params', 'conditions']:
                            if isinstance(rule.get(field), str):
                                rule[field] = json.loads(rule[field])
                        if isinstance(rule.get('edited_parameters'), str):
                            rule['edited_parameters'] = json.loads(rule['edited_parameters'])
                        # Convert target_columns from PostgreSQL array string
                        if 'target_columns' in rule and rule['target_columns'] is not None:
                            if isinstance(rule['target_columns'], str):
                                # Parse PostgreSQL array format {col1,col2}
                                arr_str = rule['target_columns']
                                if arr_str.startswith('{') and arr_str.endswith('}'):
                                    rule['target_columns'] = [
                                        x.strip('"') for x in arr_str[1:-1].split(',')
                                        if x.strip('"')
                                    ]
                        rules.append(rule)
                    return rules
        except Exception as e:
            logger.error(f"Failed to get rules: {e}")
            return []

    def update_rule_status(self, rule_id: str, status: str, edited_parameters: Optional[Dict] = None) -> bool:
        """
        Cập nhật trạng thái của một rule.

        Args:
            rule_id: ID của rule
            status: Trạng thái mới
            edited_parameters: Parameters đã edit (nếu có)

        Returns:
            True nếu thành công
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    if edited_parameters:
                        cur.execute("""
                            UPDATE dq_rules
                            SET status = %s, edited_parameters = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE rule_id = %s
                        """, (status, json.dumps(edited_parameters), rule_id))
                    else:
                        cur.execute("""
                            UPDATE dq_rules
                            SET status = %s, updated_at = CURRENT_TIMESTAMP
                            WHERE rule_id = %s
                        """, (status, rule_id))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            logger.error(f"Failed to update rule status: {e}")
            return False

    def delete_rules(self, table_name: str, engine: Optional[str] = None) -> int:
        """
        Xóa rules theo table và engine.

        Args:
            table_name: Tên bảng
            engine: 'BASIC', 'ADVANCED', hoặc None (xóa tất cả)

        Returns:
            Số lượng đã xóa
        """
        try:
            with self._get_connection() as conn:
                with conn.cursor() as cur:
                    if engine:
                        cur.execute(
                            "DELETE FROM dq_rules WHERE table_name = %s AND engine = %s",
                            (table_name, engine)
                        )
                    else:
                        cur.execute(
                            "DELETE FROM dq_rules WHERE table_name = %s",
                            (table_name,)
                        )
                    conn.commit()
                    deleted = cur.rowcount
                    logger.info(f"Deleted {deleted} rules for table {table_name}")
                    return deleted
        except Exception as e:
            logger.error(f"Failed to delete rules: {e}")
            return 0


# Singleton instance
db_service = DatabaseService()
