"""Main SQL Mapper cho Advanced Data Quality Rules.

Chuyen doi structured rule output tu LLM thanh executable SQL.

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
from backend.engine.sql_mapper.condition_compiler import (
    compile_condition,
    compile_conditional_atomic,
)
from backend.engine.sql_mapper.sql_utils import quote_identifier, combine_and, combine_or, build_select_sql
from backend.engine.sql_mapper.validator import validate_advanced_rule

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

        Semantic:
        - if[] noi bang AND
        - then[] noi bang AND
        - Violation cua branch = IF_GROUP AND NOT(THEN_GROUP)
        - Violation cua rule = OR(tat ca violations)

        Args:
            conditions: List of branches (moi branch co "if" va "then")

        Returns:
            Violation predicate string

        Raises:
            MapperError: Khi format khong dung hoac thieu du lieu
        """
        # Check for new format (branches with if/then)
        if not conditions:
            raise MapperError("CONDITIONAL_DEPENDENCY requires non-empty conditions")

        # Detect format: new format co "if" key, old format co "role" key
        first_item = conditions[0]
        if "if" in first_item or "then" in first_item:
            # New format: branches
            return self._compile_conditional_branches(conditions, ctx)
        elif "role" in first_item:
            # Old format: flat conditions with role
            raise MapperError(
                "CONDITIONAL_DEPENDENCY now expects conditions as IF-THEN branches; "
                "legacy flat conditions using role/type are not supported."
            )
        else:
            raise MapperError(
                "CONDITIONAL_DEPENDENCY conditions must be IF-THEN branches "
                "with 'if' and 'then' arrays"
            )

    def _compile_conditional_branches(
        self,
        branches: list[dict[str, Any]],
        ctx: CompileContext,
    ) -> str:
        """Compile IF-THEN branches format.

        Args:
            branches: List of {if: [...], then: [...]} objects
            ctx: Compile context

        Returns:
            Violation predicate string
        """
        branch_violations = []

        for branch in branches:
            # Validate branch structure
            if "if" not in branch:
                raise MapperError("Branch missing 'if' array")
            if "then" not in branch:
                raise MapperError("Branch missing 'then' array")

            if_conditions = branch["if"]
            then_conditions = branch["then"]

            if not if_conditions:
                raise MapperError("Branch 'if' array cannot be empty")
            if not then_conditions:
                raise MapperError("Branch 'then' array cannot be empty")

            # Compile IF group (no negation)
            # IF(A AND B AND ...) = A AND B AND ...
            if_preds = [
                compile_conditional_atomic(c, ctx, negate=False)
                for c in if_conditions
            ]
            if_group = combine_and(if_preds) if len(if_preds) > 1 else if_preds[0]

            # Compile THEN violation group
            # NOT(C AND D AND ...) = NOT(C) OR NOT(D) OR ...
            then_violations = [
                compile_conditional_atomic(c, ctx, negate=True)
                for c in then_conditions
            ]
            then_violation_group = (
                combine_or(then_violations)
                if len(then_violations) > 1
                else then_violations[0]
            )

            # Branch violation = IF_GROUP AND NOT(THEN_GROUP)
            branch_violation = f"({if_group}) AND ({then_violation_group})"
            branch_violations.append(branch_violation)

        # Total violation = OR(branch_1_violation OR branch_2_violation OR ...)
        if len(branch_violations) == 1:
            return branch_violations[0]
        return combine_or(branch_violations)

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
