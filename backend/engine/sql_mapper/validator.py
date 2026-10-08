"""Validator cho Advanced Rules SQL Mapper.

Validation rieng cho moi rule type:
- TEMPORAL: Temporal ordering conditions
- CROSS_COLUMN: Cross-column comparisons
- CONDITIONAL_DEPENDENCY: IF-THEN branches (format moi)
"""

from __future__ import annotations

from typing import Any

from backend.engine.sql_mapper.operator_maps import (
    RULE_CONDITION_MATRIX,
    SUPPORTED_COMPARISON_OPS,
    SUPPORTED_NULL_OPS,
    SUPPORTED_SET_OPS,
)


class ValidationError(Exception):
    """Raised when validation fails."""
    pass


SUPPORTED_CONDITION_TYPES = {
    "COMPARISON",
    "NULL_CHECK",
    "SET",
    "ARITHMETIC",
    "TEMPORAL_ORDER",
    "DURATION",
}
SUPPORTED_RULE_TYPES = {"CROSS_COLUMN", "CONDITIONAL_DEPENDENCY", "TEMPORAL"}
ALL_ATOMIC_OPS = SUPPORTED_COMPARISON_OPS | SUPPORTED_SET_OPS | SUPPORTED_NULL_OPS
LEGACY_CONDITIONAL_FIELDS = {"role", "type", "column", "values"}


def validate_advanced_rule(rule: dict[str, Any]) -> list[str]:
    """Validate an advanced rule according to its rule-specific contract."""
    errors: list[str] = []

    if not isinstance(rule, dict):
        return ["Rule must be an object"]

    if (
        "table" not in rule
        or not isinstance(rule.get("table"), str)
        or not rule.get("table")
    ):
        errors.append("Missing required field: table")

    columns = rule.get("columns")
    if "columns" not in rule:
        errors.append("Missing required field: columns")
    elif not isinstance(columns, list) or not columns:
        errors.append("Field 'columns' must be a non-empty list")
    elif any(not isinstance(column, str) or not column for column in columns):
        errors.append("Field 'columns' must contain non-empty strings")

    rule_type = rule.get("rule_type")
    if "rule_type" not in rule:
        errors.append("Missing required field: rule_type")
    elif rule_type not in SUPPORTED_RULE_TYPES:
        errors.append(f"Unsupported rule_type: {rule_type}")

    conditions = rule.get("conditions")
    if "conditions" not in rule:
        errors.append("Missing required field: conditions")
    elif not isinstance(conditions, list) or not conditions:
        errors.append("Field 'conditions' must be a non-empty list")

    if errors:
        return errors

    if rule_type == "CONDITIONAL_DEPENDENCY":
        return _validate_conditional(conditions, set(columns))

    allowed_types = RULE_CONDITION_MATRIX.get(rule_type, set())
    for index, condition in enumerate(conditions):
        errors.extend(
            _validate_legacy_condition(condition, rule_type, allowed_types, index)
        )

    return errors


def _validate_legacy_condition(
    condition: dict[str, Any],
    rule_type: str,
    allowed_types: set[str],
    index: int,
) -> list[str]:
    """Validate the existing CROSS_COLUMN and TEMPORAL condition formats."""
    prefix = f"Condition[{index}]"
    if not isinstance(condition, dict):
        return [f"{prefix}: condition must be an object"]
    if "type" not in condition:
        return [f"{prefix}: Missing 'type' field"]

    condition_type = condition["type"]
    if condition_type not in SUPPORTED_CONDITION_TYPES:
        return [f"{prefix}: Unsupported condition type: {condition_type}"]
    if condition_type not in allowed_types:
        return [
            f"{prefix}: Condition type '{condition_type}' is not allowed for "
            f"rule type '{rule_type}'. Allowed: {allowed_types}"
        ]

    validators = {
        "COMPARISON": _validate_comparison,
        "NULL_CHECK": _validate_null_check,
        "SET": _validate_set,
        "ARITHMETIC": _validate_arithmetic,
        "TEMPORAL_ORDER": _validate_temporal_order,
        "DURATION": _validate_duration,
    }
    return validators[condition_type](condition, prefix)


def _validate_comparison(condition: dict[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
    if "left" not in condition:
        errors.append(f"{prefix}: COMPARISON missing 'left' field")
    if "operator" not in condition:
        errors.append(f"{prefix}: COMPARISON missing 'operator' field")
    if "right" not in condition:
        errors.append(f"{prefix}: COMPARISON missing 'right' field")
    elif not isinstance(condition["right"], dict):
        errors.append(
            f"{prefix}: COMPARISON 'right' must be an object with 'type' and 'value'"
        )
    return errors


def _validate_null_check(condition: dict[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
    if "column" not in condition:
        errors.append(f"{prefix}: NULL_CHECK missing 'column' field")
    if "operator" not in condition:
        errors.append(f"{prefix}: NULL_CHECK missing 'operator' field")
    elif condition["operator"] not in SUPPORTED_NULL_OPS:
        errors.append(f"{prefix}: NULL_CHECK invalid operator: {condition['operator']}")
    return errors


def _validate_set(condition: dict[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
    if "left" not in condition:
        errors.append(f"{prefix}: SET missing 'left' field")
    if "operator" not in condition:
        errors.append(f"{prefix}: SET missing 'operator' field")
    elif condition["operator"] not in SUPPORTED_SET_OPS:
        errors.append(f"{prefix}: SET invalid operator: {condition['operator']}")
    if "values" not in condition:
        errors.append(f"{prefix}: SET missing 'values' field")
    elif not isinstance(condition["values"], list):
        errors.append(f"{prefix}: SET 'values' must be a list")
    return errors


def _validate_arithmetic(condition: dict[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
    if "target" not in condition:
        errors.append(f"{prefix}: ARITHMETIC missing 'target' field")
    if "comparison_operator" not in condition:
        errors.append(f"{prefix}: ARITHMETIC missing 'comparison_operator' field")
    if "expression" not in condition:
        errors.append(f"{prefix}: ARITHMETIC missing 'expression' field")
    elif not isinstance(condition["expression"], dict):
        errors.append(f"{prefix}: ARITHMETIC expression must be an object")
    else:
        expression = condition["expression"]
        if "operator" not in expression:
            errors.append(f"{prefix}: ARITHMETIC expression missing 'operator' field")
        if "operands" not in expression:
            errors.append(f"{prefix}: ARITHMETIC expression missing 'operands' field")
        elif (
            not isinstance(expression["operands"], list)
            or len(expression["operands"]) < 2
        ):
            errors.append(
                f"{prefix}: ARITHMETIC expression must have at least 2 operands"
            )
    return errors


def _validate_temporal_order(condition: dict[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
    if "left" not in condition:
        errors.append(f"{prefix}: TEMPORAL_ORDER missing 'left' field")
    if "right" not in condition:
        errors.append(f"{prefix}: TEMPORAL_ORDER missing 'right' field")
    if "operator" not in condition:
        errors.append(f"{prefix}: TEMPORAL_ORDER missing 'operator' field")
    elif condition["operator"] not in {
        "BEFORE", "BEFORE_EQUAL", "AFTER", "AFTER_EQUAL"
    }:
        errors.append(
            f"{prefix}: TEMPORAL_ORDER invalid operator: {condition['operator']}"
        )
    return errors


def _validate_duration(condition: dict[str, Any], prefix: str) -> list[str]:
    errors: list[str] = []
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


def _validate_conditional(
    conditions: list[Any],
    declared_columns: set[str],
) -> list[str]:
    """Validate CONDITIONAL_DEPENDENCY rule.

    Format moi: conditions la array cac IF-THEN branches
    {
        "conditions": [
            {
                "if": [atomic_condition, ...],
                "then": [atomic_condition, ...]
            },
            ...
        ]
    }

    Atomic condition format:
    {
        "left": "column_name",
        "operator": "EQ | NEQ | GT | GTE | LT | LTE | IN | NOT_IN | IS_NULL | IS_NOT_NULL",
        "right": {
            "type": "literal | column | list",
            "value": ...
        }
    }
    """
    errors = []

    return _validate_conditional_branches(conditions, declared_columns)


def _validate_conditional_branches(
    branches: list[Any],
    declared_columns: set[str],
) -> list[str]:
    """Validate IF-THEN branches format."""
    errors = []

    for i, branch in enumerate(branches):
        branch_name = f"Branch[{i}]"

        # Check structure
        if not isinstance(branch, dict):
            errors.append(f"{branch_name}: branch must be an object")
            continue

        if "role" in branch or "type" in branch:
            errors.append(
                f"{branch_name}: legacy flat conditions using role/type are not supported"
            )

        # Validate 'if' array
        if "if" not in branch:
            errors.append(f"{branch_name}: missing 'if' array")
        else:
            if_conditions = branch["if"]
            if not isinstance(if_conditions, list):
                errors.append(f"{branch_name}: 'if' must be an array")
            elif len(if_conditions) == 0:
                errors.append(f"{branch_name}: 'if' array cannot be empty")
            else:
                for j, cond in enumerate(if_conditions):
                    errors.extend(
                        _validate_atomic_condition(
                            cond,
                            f"{branch_name}.if[{j}]",
                            declared_columns,
                        )
                    )

        # Validate 'then' array
        if "then" not in branch:
            errors.append(f"{branch_name}: missing 'then' array")
        else:
            then_conditions = branch["then"]
            if not isinstance(then_conditions, list):
                errors.append(f"{branch_name}: 'then' must be an array")
            elif len(then_conditions) == 0:
                errors.append(f"{branch_name}: 'then' array cannot be empty")
            else:
                for j, cond in enumerate(then_conditions):
                    errors.extend(
                        _validate_atomic_condition(
                            cond,
                            f"{branch_name}.then[{j}]",
                            declared_columns,
                        )
                    )

    return errors


def _validate_atomic_condition(
    cond: Any,
    location: str,
    declared_columns: set[str],
) -> list[str]:
    """Validate mot atomic condition.

    Format:
    {
        "left": "column_name",
        "operator": "OP",
        "right": {...}  // null for IS_NULL/IS_NOT_NULL
    }
    """
    errors = []

    if not isinstance(cond, dict):
        errors.append(f"{location}: must be an object")
        return errors

    legacy_fields = sorted(LEGACY_CONDITIONAL_FIELDS.intersection(cond))
    if legacy_fields:
        errors.append(
            f"{location}: legacy fields are not supported: {', '.join(legacy_fields)}"
        )

    left = cond.get("left")
    if not isinstance(left, str) or not left:
        errors.append(f"{location}: missing 'left' column")
    elif left not in declared_columns:
        errors.append(f"{location}: column '{left}' is not declared in rule.columns")

    op = cond.get("operator")
    if not op:
        errors.append(f"{location}: missing 'operator'")
    elif op not in ALL_ATOMIC_OPS:
        errors.append(
            f"{location}: unsupported operator '{op}'; "
            f"valid: {sorted(ALL_ATOMIC_OPS)}"
        )
        return errors

    # Validate right based on operator
    if op in SUPPORTED_NULL_OPS:
        if "right" not in cond or cond["right"] is not None:
            errors.append(f"{location}: {op} requires 'right' to be null")
    elif op in SUPPORTED_SET_OPS:
        errors.extend(_validate_list_operand(cond.get("right"), location))
    elif op in SUPPORTED_COMPARISON_OPS:
        errors.extend(
            _validate_operand(cond.get("right"), location, declared_columns)
        )

    return errors


def _validate_operand(
    operand: Any,
    location: str,
    declared_columns: set[str],
) -> list[str]:
    """Validate an operand (literal or column)."""
    errors = []

    if not isinstance(operand, dict):
        errors.append(f"{location}.right: must be an object with 'type' and 'value'")
        return errors

    if "type" not in operand:
        errors.append(f"{location}.right: missing 'type'")
    if "value" not in operand:
        errors.append(f"{location}.right: missing 'value'")
    if "type" not in operand or "value" not in operand:
        return errors

    operand_type = operand["type"]
    if operand_type not in {"literal", "column"}:
        errors.append(
            f"{location}.right.type: expected 'literal' or 'column', got '{operand_type}'"
        )

    value = operand["value"]
    if operand_type == "literal" and value is None:
        errors.append(
            f"{location}.right.value: null literals must use IS_NULL or IS_NOT_NULL"
        )
    elif operand_type == "column":
        if not isinstance(value, str) or not value:
            errors.append(
                f"{location}.right.value: column name must be a non-empty string"
            )
        elif value not in declared_columns:
            errors.append(
                f"{location}: column '{value}' is not declared in rule.columns"
            )

    return errors


def _validate_list_operand(operand: Any, location: str) -> list[str]:
    """Validate a list operand (for IN/NOT_IN)."""
    errors = []

    if not isinstance(operand, dict):
        errors.append(f"{location}.right: must be an object")
        return errors

    if "type" not in operand:
        errors.append(f"{location}.right: missing 'type'")
    if "value" not in operand:
        errors.append(f"{location}.right: missing 'value'")
    if "type" not in operand or "value" not in operand:
        return errors

    if operand["type"] != "list":
        errors.append(f"{location}.right.type: expected 'list' for IN/NOT_IN operators")

    value = operand["value"]
    if not isinstance(value, list):
        errors.append(f"{location}.right.value: must be an array for IN/NOT_IN")
    elif len(value) == 0:
        errors.append(f"{location}.right.value: non-empty array required for IN/NOT_IN")

    return errors
