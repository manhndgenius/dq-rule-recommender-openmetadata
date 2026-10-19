"""Stable identities used to upsert generated candidates safely."""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Mapping


def normalize_sql(sql: str | None) -> str:
    return re.sub(r"\s+", " ", (sql or "").strip()).lower()


def rule_fingerprint(table_fqn: str, engine: str, rule: Mapping[str, Any]) -> str:
    payload = {
        "table_fqn": table_fqn,
        "engine": engine,
        "rule_type": rule.get("rule_type"),
        "columns": sorted(rule.get("target_columns") or rule.get("columns") or []),
        "parameters": rule.get("parameters") or {},
        "conditions": rule.get("conditions") or [],
        "sql": normalize_sql(rule.get("rendered_sql") or rule.get("sql")),
    }
    encoded = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def stable_rule_id(table_fqn: str, engine: str, rule: Mapping[str, Any]) -> str:
    return f"{engine.lower()}_{rule_fingerprint(table_fqn, engine, rule)[:20]}"
