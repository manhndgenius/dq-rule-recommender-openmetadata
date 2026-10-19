"""Non-destructive PostgreSQL repository for normalized rule candidates."""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Dict, Iterable, List

from psycopg2.extras import RealDictCursor

from backend.contracts.candidate_rule import CandidateRule
from backend.storage.db_service import db_service
from backend.storage.rule_identity import rule_fingerprint, stable_rule_id

logger = logging.getLogger(__name__)
PRESERVED_STATUSES = {"ACCEPTED", "EDITED", "REJECTED", "APPLIED"}


class RuleRepository:
    def __init__(self):
        self._initialized = False
        self._schema_lock = threading.Lock()

    def _connection(self):
        return db_service._get_connection()

    def ensure_schema(self) -> None:
        if self._initialized:
            return
        with self._schema_lock:
            if self._initialized:
                return
            with self._connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT to_regclass('public.dq_rules')")
                    if cursor.fetchone()[0] is None:
                        raise RuntimeError(
                            "dq_rules is missing; run scripts/migrate_database.py"
                        )
            self._initialized = True

    @staticmethod
    def _json(value: Any, fallback: Any) -> str:
        return json.dumps(fallback if value is None else value, default=str)

    @staticmethod
    def _candidate(row: Dict[str, Any]) -> Dict[str, Any]:
        payload = {
            field: row[field]
            for field in CandidateRule.model_fields
            if field in row and row[field] is not None
        }
        payload["id"] = row["rule_id"]
        payload["target_columns"] = row.get("target_columns") or []
        payload["reason"] = row.get("reason") or ""
        created_at = row.get("created_at")
        if created_at is not None:
            payload["created_at"] = (
                created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else str(created_at)
            )
        return CandidateRule.model_validate(payload).model_dump()

    def save_rules(
        self,
        table_fqn: str,
        engine: str,
        rules: Iterable[Dict[str, Any]],
        generation_metadata: Dict[str, Any] | None = None,
    ) -> Dict[str, int]:
        prepared = []
        for raw in rules:
            rule = dict(raw)
            rule["table_fqn"] = table_fqn
            rule["table_name"] = rule.get("table_name") or table_fqn.split(".")[-1]
            rule["engine"] = engine
            rule["generation_metadata"] = generation_metadata or {}
            rule["rule_fingerprint"] = rule_fingerprint(table_fqn, engine, rule)
            rule["id"] = stable_rule_id(table_fqn, engine, rule)
            prepared.append(rule)

        counts = {"saved": len(prepared), "inserted": 0, "updated": 0, "preserved": 0}
        if not prepared:
            return counts

        self.ensure_schema()
        with self._connection() as conn:
            with conn.cursor() as cursor:
                for rule in prepared:
                    counts[self._upsert(cursor, rule)] += 1
            conn.commit()
        return counts

    def _upsert(self, cursor, rule: Dict[str, Any]) -> str:
        identity = (rule["table_fqn"], rule["engine"], rule["rule_fingerprint"])
        columns = rule.get("target_columns") or rule.get("columns") or []

        # Parameters are part of the fingerprint. When generation changes a
        # parameter set, remove only the obsolete unreviewed version of that
        # same logical rule. Reviewed/APPLIED records remain untouched.
        cursor.execute(
            "DELETE FROM dq_rules WHERE table_fqn=%s AND engine=%s "
            "AND rule_type=%s AND target_columns=%s AND status='DRAFT' "
            "AND rule_fingerprint<>%s",
            (
                rule["table_fqn"],
                rule["engine"],
                rule.get("rule_type"),
                columns,
                rule["rule_fingerprint"],
            ),
        )
        cursor.execute(
            "SELECT status FROM dq_rules WHERE table_fqn=%s AND engine=%s "
            "AND rule_fingerprint=%s FOR UPDATE",
            identity,
        )
        current = cursor.fetchone()
        common = (
            rule.get("table_name"), rule.get("rule_type"), rule.get("subtype"),
            rule.get("description"), columns,
            self._json(rule.get("parameters"), {}), rule.get("expression"),
            rule.get("confidence", 1.0), rule.get("reason"),
            self._json(rule.get("evidence"), {}),
            rule.get("validation_status", "VALID"), rule.get("validation_message"),
            rule.get("profile_metric"),
            self._json(rule.get("profile_history"), []),
            rule.get("threshold_status"),
        )
        tail = (
            rule.get("sql"), rule.get("rendered_sql"), rule.get("violation_predicate"),
            self._json(rule.get("params"), {}), self._json(rule.get("conditions"), []),
            self._json(rule.get("edited_parameters"), None)
            if rule.get("edited_parameters") is not None else None,
            self._json(rule.get("generation_metadata"), {}),
        )

        if current:
            old_status = current[0]
            preserve = old_status in PRESERVED_STATUSES
            cursor.execute(
                """
                UPDATE dq_rules SET table_name=%s, rule_type=%s, subtype=%s,
                    description=%s, target_columns=%s, parameters=%s,
                    expression=%s, confidence=%s, reason=%s, evidence=%s,
                    validation_status=%s, validation_message=%s,
                    profile_metric=%s, profile_history=%s, threshold_status=%s,
                    status=%s, sql=%s, rendered_sql=%s,
                    violation_predicate=%s, params=%s, conditions=%s,
                    edited_parameters=COALESCE(edited_parameters,%s),
                    generation_metadata=%s, updated_at=CURRENT_TIMESTAMP
                WHERE table_fqn=%s AND engine=%s AND rule_fingerprint=%s
                """,
                common + ((old_status if preserve else rule.get("status", "DRAFT")),) + tail + identity,
            )
            return "preserved" if preserve else "updated"

        cursor.execute(
            """
            INSERT INTO dq_rules (
                rule_id, table_name, table_fqn, rule_type, subtype,
                description, target_columns, parameters, expression, engine, confidence,
                reason, evidence, validation_status, validation_message, status,
                profile_metric, profile_history, threshold_status,
                sql, rendered_sql, violation_predicate, params, conditions,
                edited_parameters, rule_fingerprint, generation_metadata
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                      %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                rule["id"], rule["table_name"], rule["table_fqn"],
                rule.get("rule_type"), rule.get("subtype"),
                rule.get("description"), columns,
                self._json(rule.get("parameters"), {}), rule.get("expression"),
                rule["engine"], rule.get("confidence", 1.0), rule.get("reason"),
                self._json(rule.get("evidence"), {}),
                rule.get("validation_status", "VALID"), rule.get("validation_message"),
                rule.get("status", "DRAFT"), rule.get("profile_metric"),
                self._json(rule.get("profile_history"), []),
                rule.get("threshold_status"), *tail[:5], tail[5],
                rule["rule_fingerprint"], tail[6],
            ),
        )
        return "inserted"

    def get_rules(self, table_fqn: str, engine: str | None = None) -> List[Dict[str, Any]]:
        self.ensure_schema()
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                params: List[Any] = [table_fqn, table_fqn.split(".")[-1]]
                query = (
                    "SELECT * FROM dq_rules WHERE "
                    "(table_fqn=%s OR (table_fqn IS NULL AND table_name=%s))"
                )
                if engine:
                    query += " AND engine=%s"
                    params.append(engine)
                query += " ORDER BY id"
                cursor.execute(query, params)
                return [self._candidate(dict(row)) for row in cursor.fetchall()]

    def get_rule(self, rule_id: str) -> Dict[str, Any] | None:
        self.ensure_schema()
        with self._connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute("SELECT * FROM dq_rules WHERE rule_id=%s", (rule_id,))
                row = cursor.fetchone()
                return self._candidate(dict(row)) if row else None

    def update_status(
        self,
        rule_id: str,
        status: str,
        edited_parameters: Dict[str, Any] | None = None,
    ) -> bool:
        self.ensure_schema()
        with self._connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE dq_rules SET status=%s, edited_parameters=COALESCE(%s,edited_parameters), "
                    "updated_at=CURRENT_TIMESTAMP WHERE rule_id=%s",
                    (
                        status,
                        self._json(edited_parameters, {}) if edited_parameters is not None else None,
                        rule_id,
                    ),
                )
                changed = cursor.rowcount > 0
            conn.commit()
        return changed


rule_repository = RuleRepository()
