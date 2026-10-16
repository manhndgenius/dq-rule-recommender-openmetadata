"""
Module B — Heuristic Pre-filter.

Đơn giản: chỉ hard filter C1→C4, không semantic scoring.
Mỗi cột → 0-3 eligible (column, rule_type) pairs.
"""

from __future__ import annotations

import logging
import math
from typing import List, Optional, Tuple

from backend.contracts.table_context import ColumnContext, ColumnProfile, TableContext
from backend.engine.statistical_rules.contracts import FilteredRule, PreFilterResult

# Numeric datatypes - inline để tránh circular import
NUMERIC_DATATYPES = (
    "TINYINT", "SMALLINT", "INT", "INTEGER", "BIGINT",
    "FLOAT", "FLOAT4", "FLOAT8", "DOUBLE", "REAL",
    "DECIMAL", "NUMERIC", "NUMBER",
)

logger = logging.getLogger(__name__)


# Registry: rule_type → profile field name
RULE_TO_PROFILE_FIELD = {
    "columnValueMeanToBeBetween": "mean",
    "columnValueMedianToBeBetween": "median",
    "columnValueStdDevToBeBetween": "stddev",
}


def is_numeric_type(dtype: str) -> bool:
    """Kiểm tra dtype có phải numeric không."""
    if not dtype:
        return False
    dtype_upper = dtype.upper()
    for dt in NUMERIC_DATATYPES:
        if dtype_upper.startswith(dt):
            return True
    return False


def is_verified_identifier_or_code(col: ColumnContext) -> bool:
    """
    C2: Chỉ loại nếu có bằng chứng CHẮC CHẮN là identifier/code.
    Thận trọng: không loại chỉ vì distinct_ratio cao.
    """
    # Verified PK/FK constraint
    if col.is_primary_key or col.is_foreign_key:
        return True

    # Description rõ ràng là identifier
    desc = (col.description or "").lower()
    identifier_phrases = [
        "primary key", "foreign key", "patient identifier",
        "record number", "identification number", "id number",
    ]
    for phrase in identifier_phrases:
        if phrase in desc:
            return True

    return False


def get_valid_numeric_count(profile: ColumnProfile) -> Optional[int]:
    """
    Lấy số valid observations.
    Trả về None nếu không xác minh được.
    """
    if profile.valid_count is not None:
        return profile.valid_count
    if profile.values_count is not None:
        return profile.values_count
    # Fallback: row_count - null_count
    if profile.row_count > 0:
        return max(0, profile.row_count - profile.null_count)
    return None


def is_finite_number(value: any) -> bool:
    """Kiểm tra value là số hữu hạn."""
    if value is None:
        return False
    try:
        f = float(value)
        return not math.isnan(f) and not math.isinf(f)
    except (ValueError, TypeError):
        return False


def prefilter_column(col: ColumnContext) -> PreFilterResult:
    """
    Hard filter cho một cột, trả về danh sách eligible pairs.

    Áp dụng C1→C4:
    - C1: Non-numeric → 0 pairs
    - C2: Verified identifier/code → 0 pairs
    - C3: No valid values → 0 pairs
    - Per-rule: required metric finite? StdDev needs n>=2
    """
    result = PreFilterResult(column_name=col.name)
    profile = col.profile
    dtype = col.data_type or ""

    # ========== C1: Non-numeric ==========
    if not is_numeric_type(dtype):
        return PreFilterResult(
            column_name=col.name,
            eligible_rules=[],
            filtered_rules=[
                FilteredRule(rule_type=rt, reason_code="FILTERED_NON_NUMERIC")
                for rt in RULE_TO_PROFILE_FIELD
            ],
            reason_codes=["NON_NUMERIC"],
        )

    # ========== C2: Verified identifier/code ==========
    if is_verified_identifier_or_code(col):
        return PreFilterResult(
            column_name=col.name,
            eligible_rules=[],
            filtered_rules=[
                FilteredRule(rule_type=rt, reason_code="FILTERED_IDENTIFIER_OR_CODE")
                for rt in RULE_TO_PROFILE_FIELD
            ],
            reason_codes=["IDENTIFIER_OR_CODE"],
        )

    # ========== C3: Valid values count ==========
    n = get_valid_numeric_count(profile)
    if n is None:
        return PreFilterResult(
            column_name=col.name,
            eligible_rules=[],
            filtered_rules=[
                FilteredRule(rule_type=rt, reason_code="MISSING_VALID_COUNT")
                for rt in RULE_TO_PROFILE_FIELD
            ],
            reason_codes=["MISSING_VALID_COUNT"],
        )
    if n == 0:
        return PreFilterResult(
            column_name=col.name,
            eligible_rules=[],
            filtered_rules=[
                FilteredRule(rule_type=rt, reason_code="FILTERED_NO_VALID_VALUES")
                for rt in RULE_TO_PROFILE_FIELD
            ],
            reason_codes=["NO_VALID_VALUES"],
        )

    # ========== Per-rule C4: Required metric finite ==========
    eligible = []
    filtered = []

    for rule_type, field in RULE_TO_PROFILE_FIELD.items():
        value = getattr(profile, field, None)

        # C4: Required metric present and finite
        if not is_finite_number(value):
            filtered.append(FilteredRule(
                rule_type=rule_type,
                reason_code="MISSING_OR_INVALID_PROFILE_METRIC",
            ))
            continue

        # StdDev special: needs at least 2 observations
        if rule_type == "columnValueStdDevToBeBetween" and n < 2:
            filtered.append(FilteredRule(
                rule_type=rule_type,
                reason_code="INSUFFICIENT_VALUES_FOR_STDDEV",
            ))
            continue

        # All good
        eligible.append(rule_type)

    return PreFilterResult(
        column_name=col.name,
        eligible_rules=eligible,
        filtered_rules=filtered,
        reason_codes=["NUMERIC", "VALID_PROFILE"] if eligible else [],
    )


def prefilter_table(table: TableContext) -> List[PreFilterResult]:
    """
    Pre-filter tất cả columns trong table.

    Returns:
        List of PreFilterResult (one per column)
    """
    results = []
    for col in table.columns:
        result = prefilter_column(col)
        results.append(result)

    # Log summary
    total_eligible = sum(len(r.eligible_rules) for r in results)
    columns_with_pairs = sum(1 for r in results if r.eligible_rules)
    logger.info(
        f"Table {table.table_name}: {len(results)} columns scanned, "
        f"{columns_with_pairs} with eligible pairs, "
        f"{total_eligible} total eligible pairs"
    )

    return results
