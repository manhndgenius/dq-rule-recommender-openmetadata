"""Validator cho SQL Mapper.

Validate advanced rule input theo contract.
"""

from __future__ import annotations

import logging
from typing import Any

from backend.engine.sql_mapper.operator_maps import RULE_CONDITION_MATRIX

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Raised khi rule validation thất bại."""
    pass


# Các condition types được hỗ trợ
SUPPORTED_CONDITION_TYPES = {
    "COMPARISON",
    "NULL_CHECK",
    "SET",
    "ARITHMETIC",
    "TEMPORAL_ORDER",
    "DURATION",
}

SUPPORTED_RULE_TYPES = {"CROSS_COLUMN", "CONDITIONAL_DEPENDENCY", "TEMPORAL"}


def validate_advanced_rule(rule: dict[str, Any]) -> list[str]:
    """Validate một advanced rule.

    Args:
        rule: Rule dict theo contract format

    Returns:
        List of validation error messages (empty = valid)

    Validation checks:
    1. Required fields exist
    2. rule_type is supported
    3. conditions is not empty
    4. condition types are valid for rule_type
    5. Required fields for each condition type
    """
    errors: list[str] = []

    # 1. Check required fields
    if "table" not in rule:
        errors.append("Missing required field: table")
    if "columns" not in rule:
        errors.append("Missing required field: columns")
    elif not isinstance(rule["columns"], list) or len(rule["columns"]) == 0:
        errors.append("Field 'columns' must be a non-empty list")
    if "rule_type" not in rule:
        errors.append("Missing required field: rule_type")
    elif rule["rule_type"] not in SUPPORTED_RULE_TYPES:
        errors.append(f"Unsupported rule_type: {rule['rule_type']}")
    if "conditions" not in rule:
        errors.append("Missing required field: conditions")
    elif not isinstance(rule["conditions"], list) or len(rule["conditions"]) == 0:
        errors.append("Field 'conditions' must be a non-empty list")

    if errors:
        return errors

    # 2. Validate each condition
    rule_type = rule["rule_type"]
    allowed_condition_types = RULE_CONDITION_MATRIX.get(rule_type, set())

    for i, condition in enumerate(rule["conditions"]):
        cond_errors = _validate_condition(condition, rule_type, allowed_condition_types, i)
        errors.extend(cond_errors)

    return errors


def _validate_condition(
    condition: dict[str, Any],
    rule_type: str,
    allowed_types: set[str],
    index: int,
) -> list[str]:
    """Validate một condition.

    Args:
        condition: Condition dict
        rule_type: Rule type đang validate
        allowed_types: Allowed condition types for this rule
        index: Index của condition trong list (for error messages)

    Returns:
        List of error messages
    """
    errors: list[str] = []
    prefix = f"Condition[{index}]"

    # Check condition type exists
    if "type" not in condition:
        errors.append(f"{prefix}: Missing 'type' field")
        return errors

    cond_type = condition["type"]

    # Check condition type is supported
    if cond_type not in SUPPORTED_CONDITION_TYPES:
        errors.append(f"{prefix}: Unsupported condition type: {cond_type}")
        return errors

    # Check condition type is allowed for this rule type
    if cond_type not in allowed_types:
        errors.append(
            f"{prefix}: Condition type '{cond_type}' is not allowed for rule type '{rule_type}'. "
            f"Allowed: {allowed_types}"
        )
        return errors

    # Validate based on condition type
    if cond_type == "COMPARISON":
        errors.extend(_validate_comparison(condition, prefix))
    elif cond_type == "NULL_CHECK":
        errors.extend(_validate_null_check(condition, prefix))
    elif cond_type == "SET":
        errors.extend(_validate_set(condition, prefix))
    elif cond_type == "ARITHMETIC":
        errors.extend(_validate_arithmetic(condition, prefix))
    elif cond_type == "TEMPORAL_ORDER":
        errors.extend(_validate_temporal_order(condition, prefix))
    elif cond_type == "DURATION":
        errors.extend(_validate_duration(condition, prefix))

    return errors


def _validate_comparison(condition: dict[str, Any], prefix: str) -> list[str]:
    """Validate COMPARISON condition."""
    errors = []

    if "left" not in condition:
        errors.append(f"{prefix}: COMPARISON missing 'left' field")
    if "operator" not in condition:
        errors.append(f"{prefix}: COMPARISON missing 'operator' field")
    if "right" not in condition:
        errors.append(f"{prefix}: COMPARISON missing 'right' field")
    elif not isinstance(condition["right"], dict):
        errors.append(f"{prefix}: COMPARISON 'right' must be an object with 'type' and 'value'")

    return errors


def _validate_null_check(condition: dict[str, Any], prefix: str) -> list[str]:
    """Validate NULL_CHECK condition."""
    errors = []

    if "column" not in condition:
        errors.append(f"{prefix}: NULL_CHECK missing 'column' field")
    if "operator" not in condition:
        errors.append(f"{prefix}: NULL_CHECK missing 'operator' field")
    elif condition["operator"] not in {"IS_NULL", "IS_NOT_NULL"}:
        errors.append(f"{prefix}: NULL_CHECK invalid operator: {condition['operator']}")

    return errors


def _validate_set(condition: dict[str, Any], prefix: str) -> list[str]:
    """Validate SET condition."""
    errors = []

    if "left" not in condition:
        errors.append(f"{prefix}: SET missing 'left' field")
    if "operator" not in condition:
        errors.append(f"{prefix}: SET missing 'operator' field")
    elif condition["operator"] not in {"IN", "NOT_IN"}:
        errors.append(f"{prefix}: SET invalid operator: {condition['operator']}")
    if "values" not in condition:
        errors.append(f"{prefix}: SET missing 'values' field")
    elif not isinstance(condition["values"], list):
        errors.append(f"{prefix}: SET 'values' must be a list")

    return errors


def _validate_arithmetic(condition: dict[str, Any], prefix: str) -> list[str]:
    """Validate ARITHMETIC condition."""
    errors = []

    if "target" not in condition:
        errors.append(f"{prefix}: ARITHMETIC missing 'target' field")
    if "comparison_operator" not in condition:
        errors.append(f"{prefix}: ARITHMETIC missing 'comparison_operator' field")
    if "expression" not in condition:
        errors.append(f"{prefix}: ARITHMETIC missing 'expression' field")
    else:
        expr = condition["expression"]
        if "operator" not in expr:
            errors.append(f"{prefix}: ARITHMETIC expression missing 'operator' field")
        if "operands" not in expr:
            errors.append(f"{prefix}: ARITHMETIC expression missing 'operands' field")
        elif not isinstance(expr["operands"], list) or len(expr["operands"]) < 2:
            errors.append(f"{prefix}: ARITHMETIC expression must have at least 2 operands")

    return errors


def _validate_temporal_order(condition: dict[str, Any], prefix: str) -> list[str]:
    """Validate TEMPORAL_ORDER condition."""
    errors = []

    if "left" not in condition:
        errors.append(f"{prefix}: TEMPORAL_ORDER missing 'left' field")
    if "right" not in condition:
        errors.append(f"{prefix}: TEMPORAL_ORDER missing 'right' field")
    if "operator" not in condition:
        errors.append(f"{prefix}: TEMPORAL_ORDER missing 'operator' field")
    elif condition["operator"] not in {"BEFORE", "BEFORE_EQUAL", "AFTER", "AFTER_EQUAL"}:
        errors.append(f"{prefix}: TEMPORAL_ORDER invalid operator: {condition['operator']}")

    return errors


def _validate_duration(condition: dict[str, Any], prefix: str) -> list[str]:
    """Validate DURATION condition."""
    errors = []

    if "start_column" not in condition:
        errors.append(f"{prefix}: DURATION missing 'start_column' field")
    if "end_column" not in condition:
        errors.append(f"{prefix}: DURATION missing 'end_column' field")
    if "operator" not in condition:
        errors.append(f"{prefix}: DURATION missing 'operator' field")
    if "value" not in condition:
        errors.append(f"{prefix}: DURATION missing 'value' field")
    if "unit" not in condition:
        errors.append(f"{prefix}: DURATION missing 'unit' field")
    elif condition["unit"] not in {"MINUTE", "HOUR", "DAY"}:
        errors.append(f"{prefix}: DURATION invalid unit: {condition['unit']}")

    return errors
