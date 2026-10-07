"""Main SQL Mapper cho Advanced Data Quality Rules.

Chuyển đổi structured rule output từ LLM thành executable SQL.

Target:
    LLM semantic rule (valid state)
        ↓
    SQL violation predicate
        ↓
    SELECT ... WHERE violation

Usage:
    >>> rule = {
    ...     "rule_type": "CROSS_COLUMN",
    ...     "table": "patients",
    ...     "columns": ["healthcare_coverage", "healthcare_expenses"],
    ...     "conditions": [{
    ...         "type": "COMPARISON",
    ...         "left": "healthcare_coverage",
    ...         "operator": "LTE",
    ...         "right": {"type": "column", "value": "healthcare_expenses"}
    ...     }]
    ... }
    >>> result = map_advanced_rule_to_sql(rule)
    >>> print(result["sql"])
    SELECT * FROM "patients" WHERE "healthcare_coverage" > "healthcare_expenses"
"""

from __future__ import annotations

import logging
from typing import Any

from backend.engine.sql_mapper.compile_context import CompileContext
from backend.engine.sql_mapper.condition_compiler import compile_condition
from backend.engine.sql_mapper.operator_maps import RULE_CONDITION_MATRIX
from backend.engine.sql_mapper.sql_utils import quote_identifier, combine_and, combine_or, build_select_sql
from backend.engine.sql_mapper.validator import validate_advanced_rule, ValidationError

logger = logging.getLogger(__name__)


class MapperError(Exception):
    """Raised khi mapping thất bại."""
    pass


class AdvancedRuleMapper:
    """Mapper chuyển đổi advanced rule thành SQL."""

    def __init__(self) -> None:
        """Khởi tạo mapper."""
        pass

    def map_to_sql(self, rule: dict[str, Any]) -> dict[str, Any]:
        """Map một advanced rule thành SQL.

        Args:
            rule: Rule dict theo contract format

        Returns:
            Dict với keys: rule_type, table, violation_predicate, sql, params

        Raises:
            MapperError: Khi validation thất bại hoặc mapping lỗi
        """
        # 1. Validate
        errors = validate_advanced_rule(rule)
        if errors:
            raise MapperError(f"Validation failed: {'; '.join(errors)}")

        # 2. Compile
        ctx = CompileContext()
        rule_type = rule["rule_type"]
        table = rule["table"]

        try:
            # 3. Build violation predicate based on rule type
            if rule_type == "CROSS_COLUMN":
                violation_predicate = self._compile_cross_column(rule["conditions"], ctx)
            elif rule_type == "CONDITIONAL_DEPENDENCY":
                violation_predicate = self._compile_conditional(rule["conditions"], ctx)
            elif rule_type == "TEMPORAL":
                violation_predicate = self._compile_temporal(rule["conditions"], ctx)
            else:
                raise MapperError(f"Unsupported rule type: {rule_type}")

            # 4. Build SQL
            table_quoted = quote_identifier(table)
            sql = build_select_sql(table_quoted, where_clause=violation_predicate)

        except Exception as e:
            raise MapperError(f"Compile failed: {e}") from e

        return {
            "rule_type": rule_type,
            "table": table,
            "violation_predicate": violation_predicate,
            "sql": sql,
            "params": ctx.params,
        }

    def _compile_cross_column(
        self,
        conditions: list[dict[str, Any]],
        ctx: CompileContext,
    ) -> str:
        """Compile CROSS_COLUMN rule.

        Valid: C1 AND C2 AND ...
        Violation: NOT(C1 AND C2) = (NOT C1) OR (NOT C2)

        Args:
            conditions: List of conditions
            ctx: Compile context

        Returns:
            Violation predicate string
        """
        # Compile each condition with negation
        violations = [
            compile_condition(cond, ctx, negate=True)
            for cond in conditions
        ]

        # Combine with OR (De Morgan)
        return combine_or(violations)

    def _compile_conditional(
        self,
        conditions: list[dict[str, Any]],
        ctx: CompileContext,
    ) -> str:
        """Compile CONDITIONAL_DEPENDENCY rule.

        Valid: IF_GROUP → THEN_GROUP
        Violation: IF_GROUP AND NOT(THEN_GROUP)

        Args:
            conditions: List of conditions (each has role: IF or THEN)
            ctx: Compile context

        Returns:
            Violation predicate string
        """
        # Split by role
        if_conditions = [c for c in conditions if c.get("role") == "IF"]
        then_conditions = [c for c in conditions if c.get("role") == "THEN"]

        # Require at least one IF and one THEN
        if not if_conditions:
            raise MapperError("CONDITIONAL_DEPENDENCY requires at least one IF condition")
        if not then_conditions:
            raise MapperError("CONDITIONAL_DEPENDENCY requires at least one THEN condition")

        # Compile IF group (no negation)
        if_group = combine_and([
            compile_condition(c, ctx, negate=False)
            for c in if_conditions
        ])

        # Compile THEN violation group
        # NOT(B AND C) = NOT(B) OR NOT(C)
        then_violations = [
            compile_condition(c, ctx, negate=True)
            for c in then_conditions
        ]
        then_violation_group = combine_or(then_violations)

        return f"({if_group}) AND ({then_violation_group})"

    def _compile_temporal(
        self,
        conditions: list[dict[str, Any]],
        ctx: CompileContext,
    ) -> str:
        """Compile TEMPORAL rule.

        Valid: C1 AND C2 AND ...
        Violation: NOT(C1 AND C2) = (NOT C1) OR (NOT C2)

        Args:
            conditions: List of temporal conditions
            ctx: Compile context

        Returns:
            Violation predicate string
        """
        # Same as CROSS_COLUMN
        violations = [
            compile_condition(cond, ctx, negate=True)
            for cond in conditions
        ]
        return combine_or(violations)


def map_advanced_rule_to_sql(rule: dict[str, Any]) -> dict[str, Any]:
    """Map một advanced rule thành SQL (convenience function).

    Args:
        rule: Rule dict theo contract format

    Returns:
        Dict với keys: rule_type, table, violation_predicate, sql, params

    Example:
        >>> rule = {
        ...     "rule_type": "CROSS_COLUMN",
        ...     "table": "patients",
        ...     "columns": ["healthcare_coverage", "healthcare_expenses"],
        ...     "conditions": [{
        ...         "type": "COMPARISON",
        ...         "left": "healthcare_coverage",
        ...         "operator": "LTE",
        ...         "right": {"type": "column", "value": "healthcare_expenses"}
        ...     }]
        ... }
        >>> result = map_advanced_rule_to_sql(rule)
        >>> result["sql"]
        'SELECT * FROM "patients" WHERE "healthcare_coverage" > "healthcare_expenses"'
    """
    mapper = AdvancedRuleMapper()
    return mapper.map_to_sql(rule)
