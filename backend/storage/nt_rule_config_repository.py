"""PostgreSQL repository for NT governance rule configuration overrides."""

from __future__ import annotations

import copy
import json
import threading
from typing import Any, Dict, Optional

from psycopg2.extras import RealDictCursor

from backend.engine.nt_rules.config import DEFAULT_RULE_CONFIG
from backend.engine.nt_rules.validation import validate_nt_rule_config
from backend.storage.db_service import db_service


class UnknownNTRuleError(KeyError):
    pass


class InvalidNTRuleConfigError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("Invalid NT rule configuration")
        self.errors = errors


class NTRuleConfigConflictError(RuntimeError):
    def __init__(self, expected_version: int, current_version: int):
        super().__init__(
            f"Expected version {expected_version}, current version is "
            f"{current_version}"
        )
        self.expected_version = expected_version
        self.current_version = current_version


class NTRuleConfigRepository:
    def __init__(self) -> None:
        self._initialized = False
        self._schema_lock = threading.Lock()

    def _connection(self):
        return db_service.connection()

    def ensure_schema(self) -> None:
        if self._initialized:
            return
        with self._schema_lock:
            if self._initialized:
                return
            with self._connection() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT to_regclass('public.nt_rule_configs')"
                    )
                    if cursor.fetchone()[0] is None:
                        raise RuntimeError(
                            "nt_rule_configs is missing; run "
                            "scripts/migrate_database.py"
                        )
            self._initialized = True

    @staticmethod
    def _assert_known_rule(rule_name: str) -> None:
        if rule_name not in DEFAULT_RULE_CONFIG:
            raise UnknownNTRuleError(rule_name)

    @staticmethod
    def _effective_config(
        rule_name: str,
        override: Dict[str, Any],
    ) -> Dict[str, Any]:
        effective = copy.deepcopy(DEFAULT_RULE_CONFIG[rule_name])
        effective.update(copy.deepcopy(override))
        return effective

    @classmethod
    def _normalize_override(
        cls,
        rule_name: str,
        config: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        effective = cls._effective_config(rule_name, config)
        errors = validate_nt_rule_config(rule_name, effective)
        if errors:
            raise InvalidNTRuleConfigError(errors)
        defaults = DEFAULT_RULE_CONFIG[rule_name]
        override = {
            name: copy.deepcopy(value)
            for name, value in effective.items()
            if name not in defaults or value != defaults[name]
        }
        return effective, override

    @classmethod
    def _response(
        cls,
        rule_name: str,
        row: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        override = copy.deepcopy(row.get("config") or {}) if row else {}
        return {
            "rule_name": rule_name,
            "config": cls._effective_config(rule_name, override),
            "override": override,
            "enabled": row["enabled"] if row else True,
            "version": row["version"] if row else 0,
            "persisted": row is not None,
            "updated_by": row.get("updated_by") if row else None,
            "created_at": row.get("created_at") if row else None,
            "updated_at": row.get("updated_at") if row else None,
        }

    def get(self, rule_name: str) -> Dict[str, Any]:
        self._assert_known_rule(rule_name)
        self.ensure_schema()
        with self._connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(
                    "SELECT * FROM nt_rule_configs WHERE rule_name=%s",
                    (rule_name,),
                )
                row = cursor.fetchone()
        return self._response(rule_name, dict(row) if row else None)

    def list_all(self) -> list[Dict[str, Any]]:
        self.ensure_schema()
        with self._connection() as connection:
            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM nt_rule_configs")
                rows = {
                    row["rule_name"]: dict(row)
                    for row in cursor.fetchall()
                }
        return [
            self._response(rule_name, rows.get(rule_name))
            for rule_name in DEFAULT_RULE_CONFIG
        ]

    def upsert(
        self,
        rule_name: str,
        config: Dict[str, Any],
        expected_version: int,
        enabled: bool = True,
        updated_by: Optional[str] = None,
    ) -> Dict[str, Any]:
        self._assert_known_rule(rule_name)
        _, override = self._normalize_override(rule_name, config)
        self.ensure_schema()

        with self._connection() as connection:
            with connection.cursor() as cursor:
                if expected_version == 0:
                    cursor.execute(
                        """
                        INSERT INTO nt_rule_configs (
                            rule_name, config, enabled, version, updated_by
                        ) VALUES (%s, %s, %s, 1, %s)
                        ON CONFLICT (rule_name) DO NOTHING
                        """,
                        (
                            rule_name,
                            json.dumps(override),
                            enabled,
                            updated_by,
                        ),
                    )
                else:
                    cursor.execute(
                        """
                        UPDATE nt_rule_configs
                        SET config=%s, enabled=%s, version=version+1,
                            updated_by=%s, updated_at=NOW()
                        WHERE rule_name=%s AND version=%s
                        """,
                        (
                            json.dumps(override),
                            enabled,
                            updated_by,
                            rule_name,
                            expected_version,
                        ),
                    )
                if cursor.rowcount == 0:
                    cursor.execute(
                        "SELECT version FROM nt_rule_configs WHERE rule_name=%s",
                        (rule_name,),
                    )
                    current = cursor.fetchone()
                    raise NTRuleConfigConflictError(
                        expected_version,
                        current[0] if current else 0,
                    )
        return self.get(rule_name)

    def delete(self, rule_name: str, expected_version: int) -> Dict[str, Any]:
        self._assert_known_rule(rule_name)
        self.ensure_schema()
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM nt_rule_configs "
                    "WHERE rule_name=%s AND version=%s",
                    (rule_name, expected_version),
                )
                if cursor.rowcount == 0:
                    cursor.execute(
                        "SELECT version FROM nt_rule_configs WHERE rule_name=%s",
                        (rule_name,),
                    )
                    current = cursor.fetchone()
                    current_version = current[0] if current else 0
                    if expected_version == 0 and current_version == 0:
                        return self._response(rule_name, None)
                    raise NTRuleConfigConflictError(
                        expected_version,
                        current_version,
                    )
        return self._response(rule_name, None)


nt_rule_config_repository = NTRuleConfigRepository()
