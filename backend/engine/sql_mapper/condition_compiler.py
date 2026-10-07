"""Condition Compiler cho SQL Mapper.

Biên dịch các condition objects thành SQL predicates.

Condition types:
- COMPARISON: column-to-column hoặc column-to-literal comparison
- NULL_CHECK: IS NULL / IS NOT NULL
- SET: IN / NOT IN
- ARITHMETIC: arithmetic expressions
- TEMPORAL_ORDER: date/time ordering
- DURATION: duration between timestamps
"""

from __future__ import annotations

import logging
from typing import Any

from backend.engine.sql_mapper.compile_context import CompileContext
from backend.engine.sql_mapper.operator_maps import (
    SQL_COMPARISON_OPERATORS,
    SQL_ARITHMETIC_OPERATORS,
    SQL_NULL_OPERATORS,
    DURATION_UNITS,
    SUPPORTED_COMPARISON_OPS,
    SUPPORTED_NULL_OPS,
    SUPPORTED_ARITHMETIC_OPS,
    SUPPORTED_TEMPORAL_OPS,
    SUPPORTED_DURATION_UNITS,
)
from backend.engine.sql_mapper.sql_utils import quote_identifier

logger = logging.getLogger(__name__)


# =============================================================================
# Compile Functions
# =============================================================================

def compile_comparison(
    condition: dict[str, Any],
    ctx: CompileContext,
    negate: bool = False,
) -> str:
    """Compile COMPARISON condition.

    Args:
        condition: Dict với keys: type, left, operator, right
        ctx: Compile context để bind parameters
        negate: True = violation, False = valid

    Returns:
        SQL predicate string

    Raises:
        ValueError: Khi operator không được hỗ trợ

    Examples:
        # Column to column
        compile_comparison({
            "type": "COMPARISON",
            "left": "healthcare_coverage",
            "operator": "LTE",
            "right": {"type": "column", "value": "healthcare_expenses"}
        })
        # → "healthcare_coverage" <= "healthcare_expenses"
    """
    operator = condition["operator"]

    if operator not in SUPPORTED_COMPARISON_OPS:
        raise ValueError(f"Unsupported comparison operator: {operator}")

    # Negate operator nếu cần
    if negate:
        _negated_ops = {
            "EQ": "NEQ", "NEQ": "EQ",
            "GT": "LTE", "LTE": "GT",
            "GTE": "LT", "LT": "GTE",
        }
        operator = _negated_ops[operator]

    left_col = quote_identifier(condition["left"])
    sql_op = SQL_COMPARISON_OPERATORS[operator]
    right = _compile_operand(condition["right"], ctx)

    return f"{left_col} {sql_op} {right}"


def compile_null_check(
    condition: dict[str, Any],
    ctx: CompileContext,
    negate: bool = False,
) -> str:
    """Compile NULL_CHECK condition.

    Args:
        condition: Dict với keys: type, column, operator
        ctx: Compile context
        negate: True = violation, False = valid

    Returns:
        SQL predicate string

    Examples:
        compile_null_check({"type": "NULL_CHECK", "column": "deathdate", "operator": "IS_NOT_NULL"})
        # → "deathdate" IS NOT NULL
    """
    operator = condition["operator"]

    if operator not in SUPPORTED_NULL_OPS:
        raise ValueError(f"Unsupported null operator: {operator}")

    # Negate operator nếu cần
    if negate:
        _negated = {"IS_NULL": "IS_NOT_NULL", "IS_NOT_NULL": "IS_NULL"}
        operator = _negated[operator]

    column = quote_identifier(condition["column"])
    sql_op = SQL_NULL_OPERATORS[operator]

    return f"{column} {sql_op}"


def compile_set(
    condition: dict[str, Any],
    ctx: CompileContext,
    negate: bool = False,
) -> str:
    """Compile SET condition (IN / NOT IN).

    Args:
        condition: Dict với keys: type, left, operator, values
        ctx: Compile context
        negate: True = violation, False = valid

    Returns:
        SQL predicate string

    Examples:
        compile_set({
            "type": "SET",
            "left": "currency",
            "operator": "IN",
            "values": ["USD", "USN"]
        })
        # → "currency" IN (:param_1, :param_2)
    """
    operator = condition["operator"]

    if operator not in {"IN", "NOT_IN"}:
        raise ValueError(f"Unsupported set operator: {operator}")

    # Negate nếu cần
    if negate:
        operator = "NOT_IN" if operator == "IN" else "IN"

    left_col = quote_identifier(condition["left"])
    values = condition["values"]

    # Bind all values
    placeholders = [ctx.add_param(v) for v in values]
    values_list = ", ".join(placeholders)

    if operator == "IN":
        return f"{left_col} IN ({values_list})"
    else:
        return f"{left_col} NOT IN ({values_list})"


def compile_arithmetic(
    condition: dict[str, Any],
    ctx: CompileContext,
    negate: bool = False,
) -> str:
    """Compile ARITHMETIC condition.

    Args:
        condition: Dict với keys: type, target, comparison_operator, expression
        ctx: Compile context
        negate: True = violation, False = valid

    Returns:
        SQL predicate string

    Examples:
        compile_arithmetic({
            "type": "ARITHMETIC",
            "target": "total",
            "comparison_operator": "EQ",
            "expression": {
                "operator": "MULTIPLY",
                "operands": ["quantity", "price"]
            }
        })
        # → "total" = ("quantity" * "price")
    """
    target = quote_identifier(condition["target"])
    comparison_op = condition["comparison_operator"]

    if comparison_op not in SUPPORTED_COMPARISON_OPS:
        raise ValueError(f"Unsupported arithmetic comparison operator: {comparison_op}")

    # Negate nếu cần
    if negate:
        _negated_ops = {
            "EQ": "NEQ", "NEQ": "EQ",
            "GT": "LTE", "LTE": "GT",
            "GTE": "LT", "LT": "GTE",
        }
        comparison_op = _negated_ops[comparison_op]

    expr = condition["expression"]
    arith_op = expr["operator"]

    if arith_op not in SUPPORTED_ARITHMETIC_OPS:
        raise ValueError(f"Unsupported arithmetic operator: {arith_op}")

    operands = expr["operands"]
    sql_arith_op = SQL_ARITHMETIC_OPERATORS[arith_op]

    # Quote all operands
    quoted_operands = [quote_identifier(op) for op in operands]

    # Build expression (ADD/MULTIPLY có thể nhiều hơn 2)
    if len(quoted_operands) == 1:
        expr_sql = quoted_operands[0]
    else:
        expr_sql = "(" + f" {sql_arith_op} ".join(quoted_operands) + ")"

    sql_comp_op = SQL_COMPARISON_OPERATORS[comparison_op]

    return f"{target} {sql_comp_op} {expr_sql}"


def compile_temporal_order(
    condition: dict[str, Any],
    ctx: CompileContext,
    negate: bool = False,
) -> str:
    """Compile TEMPORAL_ORDER condition.

    Args:
        condition: Dict với keys: type, left, operator, right
        ctx: Compile context
        negate: True = violation, False = valid

    Returns:
        SQL predicate string

    Examples:
        compile_temporal_order({
            "type": "TEMPORAL_ORDER",
            "left": "birthdate",
            "operator": "BEFORE_EQUAL",
            "right": "deathdate"
        })
        # → "birthdate" <= "deathdate"
    """
    operator = condition["operator"]

    if operator not in SUPPORTED_TEMPORAL_OPS:
        raise ValueError(f"Unsupported temporal operator: {operator}")

    # Map to comparison operator
    temporal_to_sql = {
        "BEFORE": "<",
        "BEFORE_EQUAL": "<=",
        "AFTER": ">",
        "AFTER_EQUAL": ">=",
    }

    # Negate nếu cần
    if negate:
        _negated = {
            "BEFORE": "AFTER_EQUAL",
            "BEFORE_EQUAL": "AFTER",
            "AFTER": "BEFORE_EQUAL",
            "AFTER_EQUAL": "BEFORE",
        }
        operator = _negated[operator]

    left_col = quote_identifier(condition["left"])
    right_col = quote_identifier(condition["right"])
    sql_op = temporal_to_sql[operator]

    return f"{left_col} {sql_op} {right_col}"


def compile_duration(
    condition: dict[str, Any],
    ctx: CompileContext,
    negate: bool = False,
) -> str:
    """Compile DURATION condition.

    Args:
        condition: Dict với keys: type, start_column, end_column, operator, value, unit
        ctx: Compile context
        negate: True = violation, False = valid

    Returns:
        SQL predicate string

    Examples:
        compile_duration({
            "type": "DURATION",
            "start_column": "start_time",
            "end_column": "end_time",
            "operator": "LTE",
            "value": 30,
            "unit": "DAY"
        })
        # → "end_time" <= "start_time" + INTERVAL '30 DAY'
    """
    operator = condition["operator"]
    value = condition["value"]
    unit = condition["unit"]

    if unit not in SUPPORTED_DURATION_UNITS:
        raise ValueError(f"Unsupported duration unit: {unit}")

    if operator not in {"GT", "GTE", "LT", "LTE"}:
        raise ValueError(f"Unsupported duration comparison operator: {operator}")

    start_col = quote_identifier(condition["start_column"])
    end_col = quote_identifier(condition["end_column"])

    # Negate operator
    if negate:
        _negated_ops = {"GT": "LTE", "LTE": "GT", "GTE": "LT", "LT": "GTE"}
        operator = _negated_ops[operator]

    # Bind value
    bound_value = ctx.add_param(value)
    sql_op = SQL_COMPARISON_OPERATORS[operator]
    unit_sql = DURATION_UNITS[unit]

    return f'{end_col} {sql_op} {start_col} + INTERVAL \'1 {unit_sql}\' * {bound_value}'


# =============================================================================
# Dispatcher
# =============================================================================

def compile_condition(
    condition: dict[str, Any],
    ctx: CompileContext,
    negate: bool = False,
) -> str:
    """Dispatch compile cho any condition type.

    Args:
        condition: Condition dict với "type" key
        ctx: Compile context
        negate: True = violation condition

    Returns:
        SQL predicate string

    Raises:
        ValueError: Khi condition type không được hỗ trợ
    """
    condition_type = condition.get("type", "").upper()

    compiler_map = {
        "COMPARISON": compile_comparison,
        "NULL_CHECK": compile_null_check,
        "SET": compile_set,
        "ARITHMETIC": compile_arithmetic,
        "TEMPORAL_ORDER": compile_temporal_order,
        "DURATION": compile_duration,
    }

    if condition_type not in compiler_map:
        raise ValueError(f"Unsupported condition type: {condition_type}")

    return compiler_map[condition_type](condition, ctx, negate)


# =============================================================================
# Helper Functions
# =============================================================================

def _compile_operand(operand: dict[str, Any], ctx: CompileContext) -> str:
    """Compile một operand (column hoặc literal).

    Args:
        operand: Dict với keys: type (column/literal), value
        ctx: Compile context

    Returns:
        Quoted column name hoặc parameter placeholder
    """
    operand_type = operand.get("type", "column").lower()
    value = operand["value"]

    if operand_type == "column":
        return quote_identifier(value)
    elif operand_type == "literal":
        placeholder = ctx.add_param(value)
        return placeholder
    else:
        raise ValueError(f"Unknown operand type: {operand_type}")
