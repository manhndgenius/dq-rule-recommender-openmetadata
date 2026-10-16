"""Common helpers for NT governance evaluators."""

from __future__ import annotations

import re
from typing import Any, Dict, Iterable, List, Optional

from backend.contracts.nt_execution import (
    NTColumnMetadata,
    NTMetadataContext,
    NTOutcome,
    NTRuleResult,
)


def normalize_data_type(data_type: Optional[str]) -> str:
    value = re.sub(r"\s+", " ", str(data_type or "").strip().upper())
    value = re.sub(r"\(.*\)$", "", value).strip()
    aliases = {
        "BOOL": "BOOLEAN",
        "TIMESTAMP WITH TIME ZONE": "TIMESTAMPTZ",
        "TIMESTAMPZ": "TIMESTAMPTZ",
        "DATETIMEOFFSET": "TIMESTAMPTZ",
    }
    return aliases.get(value, value)


def column_map(
    context: NTMetadataContext,
    case_sensitive: bool = False,
) -> Dict[str, NTColumnMetadata]:
    if case_sensitive:
        return {column.name: column for column in context.columns}
    return {column.name.lower(): column for column in context.columns}


def filtered_columns(
    context: NTMetadataContext,
    excluded_columns: Iterable[str] = (),
    excluded_patterns: Iterable[str] = (),
) -> List[NTColumnMetadata]:
    excluded = {str(name).lower() for name in excluded_columns}
    patterns = [re.compile(pattern) for pattern in excluded_patterns]
    return [
        column
        for column in context.columns
        if column.name.lower() not in excluded
        and not any(pattern.search(column.name) for pattern in patterns)
    ]


def primary_key_columns(context: NTMetadataContext) -> List[str]:
    names: List[str] = []
    for constraint in context.table_constraints:
        constraint_type = str(
            constraint.get("constraintType") or constraint.get("type") or ""
        ).upper()
        if constraint_type == "PRIMARY_KEY":
            names.extend(str(name) for name in constraint.get("columns") or [])
    names.extend(
        column.name
        for column in context.columns
        if str(column.constraint or "").upper() == "PRIMARY_KEY"
    )
    return list(dict.fromkeys(names))


def make_result(
    definition_name: str,
    outcome: NTOutcome,
    message: str,
    *,
    expected: Optional[Dict[str, Any]] = None,
    observed: Optional[Dict[str, Any]] = None,
    evidence: Optional[Dict[str, Any]] = None,
    affected_columns: Optional[List[str]] = None,
    error_code: Optional[str] = None,
) -> NTRuleResult:
    return NTRuleResult(
        definition_name=definition_name,
        outcome=outcome,
        message=message,
        expected=expected or {},
        observed=observed or {},
        evidence=evidence or {},
        affected_columns=affected_columns or [],
        error_code=error_code,
    )
