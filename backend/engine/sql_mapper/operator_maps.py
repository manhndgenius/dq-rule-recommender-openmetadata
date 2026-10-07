"""Operator maps cho SQL Mapper.

Định nghĩa các operator mappings:
- SQL operators (toán tử SQL thực tế)
- Negated operators (toán tử phủ định)
- Arithmetic operators
- Temporal operators
"""

from typing import Final

# =============================================================================
# Comparison Operators - SQL equivalent
# =============================================================================

SQL_COMPARISON_OPERATORS: Final[dict[str, str]] = {
    "EQ": "=",
    "NEQ": "<>",
    "GT": ">",
    "GTE": ">=",
    "LT": "<",
    "LTE": "<=",
}

# =============================================================================
# Comparison Operators - Negated (for violation)
# =============================================================================

NEGATED_COMPARISON_OPERATORS: Final[dict[str, str]] = {
    "EQ": "NEQ",
    "NEQ": "EQ",
    "GT": "LTE",
    "GTE": "LT",
    "LT": "GTE",
    "LTE": "GT",
}

# =============================================================================
# Null Operators - SQL equivalent
# =============================================================================

SQL_NULL_OPERATORS: Final[dict[str, str]] = {
    "IS_NULL": "IS NULL",
    "IS_NOT_NULL": "IS NOT NULL",
}

# Null operators negation
NEGATED_NULL_OPERATORS: Final[dict[str, str]] = {
    "IS_NULL": "IS_NOT_NULL",
    "IS_NOT_NULL": "IS_NULL",
}

# =============================================================================
# Set Operators - SQL equivalent
# =============================================================================

SQL_SET_OPERATORS: Final[dict[str, str]] = {
    "IN": "IN",
    "NOT_IN": "NOT IN",
}

# Set operators negation
NEGATED_SET_OPERATORS: Final[dict[str, str]] = {
    "IN": "NOT_IN",
    "NOT_IN": "IN",
}

# =============================================================================
# Arithmetic Operators - SQL equivalent
# =============================================================================

SQL_ARITHMETIC_OPERATORS: Final[dict[str, str]] = {
    "ADD": "+",
    "SUBTRACT": "-",
    "MULTIPLY": "*",
    "DIVIDE": "/",
}

# =============================================================================
# Temporal Operators - Mapping to SQL comparison
# =============================================================================

TEMPORAL_OPERATORS: Final[dict[str, str]] = {
    "BEFORE": "LT",           # left < right
    "BEFORE_EQUAL": "LTE",    # left <= right
    "AFTER": "GT",             # left > right
    "AFTER_EQUAL": "GTE",     # left >= right
}

# Negated temporal operators
NEGATED_TEMPORAL_OPERATORS: Final[dict[str, str]] = {
    "BEFORE": "AFTER_EQUAL",  # NOT (left < right) => left >= right
    "BEFORE_EQUAL": "AFTER",  # NOT (left <= right) => left > right
    "AFTER": "BEFORE_EQUAL",  # NOT (left > right) => left <= right
    "AFTER_EQUAL": "BEFORE",  # NOT (left >= right) => left < right
}

# =============================================================================
# Duration Units - SQL INTERVAL format
# =============================================================================

DURATION_UNITS: Final[dict[str, str]] = {
    "MINUTE": "MINUTE",
    "HOUR": "HOUR",
    "DAY": "DAY",
}

# =============================================================================
# Supported Operators by Condition Type
# =============================================================================

SUPPORTED_COMPARISON_OPS = {"EQ", "NEQ", "GT", "GTE", "LT", "LTE"}
SUPPORTED_NULL_OPS = {"IS_NULL", "IS_NOT_NULL"}
SUPPORTED_SET_OPS = {"IN", "NOT_IN"}
SUPPORTED_ARITHMETIC_OPS = {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"}
SUPPORTED_TEMPORAL_OPS = {"BEFORE", "BEFORE_EQUAL", "AFTER", "AFTER_EQUAL"}
SUPPORTED_DURATION_UNITS = {"MINUTE", "HOUR", "DAY"}

# =============================================================================
# Rule-to-Condition Support Matrix
# =============================================================================

# V1 support matrix: (row = rule_type, col = condition_type)
RULE_CONDITION_MATRIX: Final[dict[str, set]] = {
    "CROSS_COLUMN": {"COMPARISON", "ARITHMETIC"},
    "CONDITIONAL_DEPENDENCY": {"COMPARISON", "NULL_CHECK", "SET"},
    "TEMPORAL": {"TEMPORAL_ORDER", "DURATION"},
}


def get_sql_operator(operator: str) -> str:
    """Get SQL equivalent of an operator."""
    if operator in SQL_COMPARISON_OPERATORS:
        return SQL_COMPARISON_OPERATORS[operator]
    if operator in SQL_NULL_OPERATORS:
        return SQL_NULL_OPERATORS[operator]
    if operator in SQL_SET_OPERATORS:
        return SQL_SET_OPERATORS[operator]
    raise ValueError(f"Unknown operator: {operator}")


def get_arithmetic_sql_operator(operator: str) -> str:
    """Get SQL equivalent of an arithmetic operator."""
    if operator not in SQL_ARITHMETIC_OPERATORS:
        raise ValueError(f"Unknown arithmetic operator: {operator}")
    return SQL_ARITHMETIC_OPERATORS[operator]


def get_negated_operator(operator: str) -> str:
    """Get negated form of an operator."""
    if operator in NEGATED_COMPARISON_OPERATORS:
        return NEGATED_COMPARISON_OPERATORS[operator]
    if operator in NEGATED_NULL_OPERATORS:
        return NEGATED_NULL_OPERATORS[operator]
    if operator in NEGATED_SET_OPERATORS:
        return NEGATED_SET_OPERATORS[operator]
    if operator in NEGATED_TEMPORAL_OPERATORS:
        return NEGATED_TEMPORAL_OPERATORS[operator]
    raise ValueError(f"Unknown operator to negate: {operator}")


def get_temporal_comparison_operator(operator: str) -> str:
    """Convert temporal operator to comparison operator."""
    if operator not in TEMPORAL_OPERATORS:
        raise ValueError(f"Unknown temporal operator: {operator}")
    return TEMPORAL_OPERATORS[operator]
