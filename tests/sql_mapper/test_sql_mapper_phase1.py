"""Tests cho SQL Mapper Phase 0 & 1 - Utilities và COMPARISON."""

import pytest

from backend.engine.sql_mapper.compile_context import CompileContext
from backend.engine.sql_mapper.operator_maps import (
    SQL_COMPARISON_OPERATORS,
    NEGATED_COMPARISON_OPERATORS,
    SQL_ARITHMETIC_OPERATORS,
    get_sql_operator,
    get_negated_operator,
    RULE_CONDITION_MATRIX,
)
from backend.engine.sql_mapper.sql_utils import (
    quote_identifier,
    combine_and,
    combine_or,
    InvalidIdentifierError,
)
from backend.engine.sql_mapper.condition_compiler import (
    compile_comparison,
    compile_arithmetic,
    compile_temporal_order,
    compile_duration,
    compile_condition,
)
from backend.engine.sql_mapper.mapper import map_advanced_rule_to_sql, MapperError


# =============================================================================
# Phase 0: Tests - CompileContext
# =============================================================================

class TestCompileContext:
    """Tests cho CompileContext."""

    def test_add_param_returns_placeholder(self):
        """add_param nên trả về placeholder unique."""
        ctx = CompileContext()

        p1 = ctx.add_param("USD")
        p2 = ctx.add_param("EUR")

        assert p1 == ":rule_param_1"
        assert p2 == ":rule_param_2"
        assert p1 != p2

    def test_add_param_stores_value(self):
        """add_param nên lưu giá trị vào params dict."""
        ctx = CompileContext()

        ctx.add_param("test_value")

        assert "rule_param_1" in ctx.params
        assert ctx.params["rule_param_1"] == "test_value"

    def test_reset_clears_params(self):
        """reset nên clear tất cả params."""
        ctx = CompileContext()
        ctx.add_param("value1")
        ctx.add_param("value2")

        ctx.reset()

        assert ctx.params == {}
        assert ctx.param_count == 0

    def test_param_count(self):
        """param_count property nên đếm đúng."""
        ctx = CompileContext()
        assert ctx.param_count == 0

        ctx.add_param("a")
        assert ctx.param_count == 1

        ctx.add_param("b")
        ctx.add_param("c")
        assert ctx.param_count == 3


# =============================================================================
# Phase 0: Tests - quote_identifier
# =============================================================================

class TestQuoteIdentifier:
    """Tests cho quote_identifier."""

    def test_simple_identifier(self):
        """Quote simple identifier."""
        assert quote_identifier("patients") == '"patients"'
        assert quote_identifier("column_name") == '"column_name"'

    def test_schema_table(self):
        """Quote schema.table format."""
        assert quote_identifier("public.patients") == '"public"."patients"'

    def test_invalid_identifier_empty(self):
        """Empty identifier nên raise."""
        with pytest.raises(InvalidIdentifierError):
            quote_identifier("")

    def test_invalid_identifier_special_chars(self):
        """Identifier với special characters nên raise."""
        with pytest.raises(InvalidIdentifierError):
            quote_identifier("column-name")

        with pytest.raises(InvalidIdentifierError):
            quote_identifier("column name")

        with pytest.raises(InvalidIdentifierError):
            quote_identifier("column;DROP TABLE")

    def test_invalid_identifier_starts_with_number(self):
        """Identifier bắt đầu bằng số nên raise."""
        with pytest.raises(InvalidIdentifierError):
            quote_identifier("123column")


# =============================================================================
# Phase 0: Tests - combine_and / combine_or
# =============================================================================

class TestCombineConditions:
    """Tests cho combine_and và combine_or."""

    def test_combine_and_single(self):
        """combine_and với 1 condition."""
        result = combine_and(["a > 1"])
        assert result == "(a > 1)"

    def test_combine_and_multiple(self):
        """combine_and với nhiều conditions."""
        result = combine_and(["a > 1", "b < 10", "c = 5"])
        assert result == "(a > 1 AND b < 10 AND c = 5)"

    def test_combine_and_empty(self):
        """combine_and với empty list."""
        result = combine_and([])
        assert result == "1=1"

    def test_combine_or_single(self):
        """combine_or với 1 condition."""
        result = combine_or(["a > 1"])
        assert result == "(a > 1)"

    def test_combine_or_multiple(self):
        """combine_or với nhiều conditions."""
        result = combine_or(["a > 1", "b > 5"])
        assert result == "(a > 1 OR b > 5)"

    def test_combine_or_empty(self):
        """combine_or với empty list."""
        result = combine_or([])
        assert result == "1=0"


# =============================================================================
# Phase 0: Tests - Operator Maps
# =============================================================================

class TestOperatorMaps:
    """Tests cho operator maps."""

    def test_sql_comparison_operators(self):
        """SQL comparison operators đúng."""
        assert SQL_COMPARISON_OPERATORS["EQ"] == "="
        assert SQL_COMPARISON_OPERATORS["NEQ"] == "<>"
        assert SQL_COMPARISON_OPERATORS["GT"] == ">"
        assert SQL_COMPARISON_OPERATORS["GTE"] == ">="
        assert SQL_COMPARISON_OPERATORS["LT"] == "<"
        assert SQL_COMPARISON_OPERATORS["LTE"] == "<="

    def test_negated_comparison_operators(self):
        """Negated operators đúng."""
        assert NEGATED_COMPARISON_OPERATORS["EQ"] == "NEQ"
        assert NEGATED_COMPARISON_OPERATORS["GT"] == "LTE"
        assert NEGATED_COMPARISON_OPERATORS["LTE"] == "GT"

    def test_get_sql_operator(self):
        """get_sql_operator hoạt động."""
        assert get_sql_operator("EQ") == "="
        assert get_sql_operator("GT") == ">"

    def test_get_negated_operator(self):
        """get_negated_operator hoạt động."""
        assert get_negated_operator("EQ") == "NEQ"
        assert get_negated_operator("GT") == "LTE"

    def test_rule_condition_matrix(self):
        """Rule-to-condition matrix đúng."""
        assert "COMPARISON" in RULE_CONDITION_MATRIX["CROSS_COLUMN"]
        assert "ARITHMETIC" in RULE_CONDITION_MATRIX["CROSS_COLUMN"]
        assert "COMPARISON" in RULE_CONDITION_MATRIX["CONDITIONAL_DEPENDENCY"]
        assert "NULL_CHECK" in RULE_CONDITION_MATRIX["CONDITIONAL_DEPENDENCY"]
        assert "TEMPORAL_ORDER" in RULE_CONDITION_MATRIX["TEMPORAL"]


# =============================================================================
# Phase 1: Tests - COMPARISON Condition
# =============================================================================

class TestComparisonCondition:
    """Tests cho COMPARISON condition compilation."""

    def test_column_to_column_lte(self):
        """Column-to-column LTE comparison."""
        ctx = CompileContext()
        condition = {
            "type": "COMPARISON",
            "left": "healthcare_coverage",
            "operator": "LTE",
            "right": {"type": "column", "value": "healthcare_expenses"}
        }

        # Valid
        result = compile_comparison(condition, ctx, negate=False)
        assert result == '"healthcare_coverage" <= "healthcare_expenses"'

        # Violation
        result = compile_comparison(condition, ctx, negate=True)
        assert result == '"healthcare_coverage" > "healthcare_expenses"'

    def test_column_to_column_eq(self):
        """Column-to-column EQ comparison."""
        ctx = CompileContext()
        condition = {
            "type": "COMPARISON",
            "left": "quantity",
            "operator": "EQ",
            "right": {"type": "column", "value": "ordered_quantity"}
        }

        result = compile_comparison(condition, ctx, negate=False)
        assert result == '"quantity" = "ordered_quantity"'

    def test_column_to_literal(self):
        """Column-to-literal comparison."""
        ctx = CompileContext()
        condition = {
            "type": "COMPARISON",
            "left": "age",
            "operator": "GTE",
            "right": {"type": "literal", "value": 18}
        }

        result = compile_comparison(condition, ctx, negate=False)
        assert result == '"age" >= :rule_param_1'
        assert ctx.params["rule_param_1"] == 18

    def test_negate_all_operators(self):
        """Test negation for all operators."""
        ctx = CompileContext()
        ops = [
            ("EQ", "NEQ"),
            ("NEQ", "EQ"),
            ("GT", "LTE"),
            ("GTE", "LT"),
            ("LT", "GTE"),
            ("LTE", "GT"),
        ]

        for original, expected_negated in ops:
            condition = {
                "type": "COMPARISON",
                "left": "col",
                "operator": original,
                "right": {"type": "column", "value": "other"}
            }
            valid = compile_comparison(condition, ctx, negate=False)
            violated = compile_comparison(condition, ctx, negate=True)

            # Check operator was negated
            assert valid != violated


# =============================================================================
# Phase 1: Tests - map_advanced_rule_to_sql
# =============================================================================

class TestMapAdvancedRuleToSql:
    """Tests cho main entry point."""

    def test_cross_column_comparison_violation(self):
        """Test CROSS_COLUMN với COMPARISON condition."""
        rule = {
            "rule_type": "CROSS_COLUMN",
            "table": "patients",
            "columns": ["healthcare_coverage", "healthcare_expenses"],
            "conditions": [
                {
                    "type": "COMPARISON",
                    "left": "healthcare_coverage",
                    "operator": "LTE",
                    "right": {"type": "column", "value": "healthcare_expenses"}
                }
            ],
            "confidence": 0.85,
            "reason": "Coverage should not exceed expenses"
        }

        result = map_advanced_rule_to_sql(rule)

        assert result["rule_type"] == "CROSS_COLUMN"
        assert result["table"] == "patients"
        assert '"healthcare_coverage" > "healthcare_expenses"' in result["violation_predicate"]
        assert "SELECT" in result["sql"]
        assert "FROM" in result["sql"]
        assert "WHERE" in result["sql"]
        assert result["params"] == {}

    def test_cross_column_multiple_comparisons(self):
        """Test CROSS_COLUMN với nhiều COMPARISON conditions.

        Valid: min <= actual AND actual <= max
        Violation: min > actual OR actual > max
        """
        rule = {
            "rule_type": "CROSS_COLUMN",
            "table": "measurements",
            "columns": ["min_value", "actual_value", "max_value"],
            "conditions": [
                {
                    "type": "COMPARISON",
                    "left": "min_value",
                    "operator": "LTE",
                    "right": {"type": "column", "value": "actual_value"}
                },
                {
                    "type": "COMPARISON",
                    "left": "actual_value",
                    "operator": "LTE",
                    "right": {"type": "column", "value": "max_value"}
                }
            ],
            "confidence": 0.9
        }

        result = map_advanced_rule_to_sql(rule)

        assert '"min_value" > "actual_value"' in result["violation_predicate"]
        assert '"actual_value" > "max_value"' in result["violation_predicate"]
        assert " OR " in result["violation_predicate"]

    def test_missing_required_field(self):
        """Validation nên catch missing fields."""
        rule = {
            "rule_type": "CROSS_COLUMN",
            # missing "table"
            "conditions": []
        }

        with pytest.raises(MapperError) as exc_info:
            map_advanced_rule_to_sql(rule)

        assert "table" in str(exc_info.value).lower()

    def test_invalid_condition_type(self):
        """Validation nên catch invalid condition type."""
        rule = {
            "rule_type": "CROSS_COLUMN",
            "table": "test",
            "columns": ["a", "b"],
            "conditions": [
                {
                    "type": "NULL_CHECK",  # Not allowed for CROSS_COLUMN
                    "column": "a",
                    "operator": "IS_NOT_NULL"
                }
            ]
        }

        with pytest.raises(MapperError) as exc_info:
            map_advanced_rule_to_sql(rule)

        assert "NULL_CHECK" in str(exc_info.value)

    def test_with_literal_parameter(self):
        """Test với literal value binding."""
        rule = {
            "rule_type": "CONDITIONAL_DEPENDENCY",
            "table": "orders",
            "columns": ["status", "amount"],
            "conditions": [
                {
                    "role": "IF",
                    "type": "COMPARISON",
                    "left": "status",
                    "operator": "EQ",
                    "right": {"type": "literal", "value": "COMPLETED"}
                },
                {
                    "role": "THEN",
                    "type": "COMPARISON",
                    "left": "amount",
                    "operator": "GT",
                    "right": {"type": "literal", "value": 0}
                }
            ],
            "confidence": 0.9
        }

        result = map_advanced_rule_to_sql(rule)

        assert len(result["params"]) == 2
        assert result["params"]["rule_param_1"] == "COMPLETED"
        assert result["params"]["rule_param_2"] == 0


# =============================================================================
# CROSS_COLUMN / ARITHMETIC Tests
# =============================================================================

class TestArithmeticCondition:
    """Tests cho ARITHMETIC condition compilation."""

    def test_multiply_two_operands(self):
        """Test multiplication với 2 operands.

        Valid: total = quantity * price
        Violation: total <> quantity * price
        """
        ctx = CompileContext()
        condition = {
            "type": "ARITHMETIC",
            "target": "total",
            "comparison_operator": "EQ",
            "expression": {
                "operator": "MULTIPLY",
                "operands": ["quantity", "price"]
            }
        }

        # Valid
        result = compile_arithmetic(condition, ctx, negate=False)
        assert result == '"total" = ("quantity" * "price")'

        # Violation
        result = compile_arithmetic(condition, ctx, negate=True)
        assert result == '"total" <> ("quantity" * "price")'

    def test_add_three_operands(self):
        """Test addition với 3 operands.

        Valid: total = subtotal + tax + shipping
        Violation: total <> subtotal + tax + shipping
        """
        ctx = CompileContext()
        condition = {
            "type": "ARITHMETIC",
            "target": "total",
            "comparison_operator": "EQ",
            "expression": {
                "operator": "ADD",
                "operands": ["subtotal", "tax", "shipping"]
            }
        }

        result = compile_arithmetic(condition, ctx, negate=True)
        assert "subtotal" in result
        assert "+" in result
        assert "tax" in result
        assert "shipping" in result
        assert "<>" in result

    def test_subtract_preserves_order(self):
        """Test subtraction giữ nguyên thứ tự operands."""
        ctx = CompileContext()
        condition = {
            "type": "ARITHMETIC",
            "target": "remaining",
            "comparison_operator": "EQ",
            "expression": {
                "operator": "SUBTRACT",
                "operands": ["total_amount", "discount"]
            }
        }

        result = compile_arithmetic(condition, ctx, negate=False)
        # Phải giữ nguyên thứ tự: total_amount - discount
        assert "total_amount" in result
        assert "-" in result
        assert "discount" in result

    def test_divide_with_comparison(self):
        """Test division với comparison operator.

        Valid: ratio = numerator / denominator
        Violation: ratio <> numerator / NULLIF(denominator, 0)
        """
        ctx = CompileContext()
        condition = {
            "type": "ARITHMETIC",
            "target": "ratio",
            "comparison_operator": "EQ",
            "expression": {
                "operator": "DIVIDE",
                "operands": ["numerator", "denominator"]
            }
        }

        result = compile_arithmetic(condition, ctx, negate=False)
        assert "ratio" in result
        assert "/" in result
        assert "numerator" in result
        assert "denominator" in result

    def test_arithmetic_with_gt_comparison(self):
        """Test arithmetic với GT comparison.

        Valid: revenue > cost * markup
        Violation: revenue <= cost * markup
        """
        ctx = CompileContext()
        condition = {
            "type": "ARITHMETIC",
            "target": "revenue",
            "comparison_operator": "GT",
            "expression": {
                "operator": "MULTIPLY",
                "operands": ["cost", "markup"]
            }
        }

        valid = compile_arithmetic(condition, ctx, negate=False)
        assert ">" in valid

        violation = compile_arithmetic(condition, ctx, negate=True)
        assert "<=" in violation

    def test_cross_column_arithmetic_rule(self):
        """Test full CROSS_COLUMN rule với ARITHMETIC condition."""
        rule = {
            "rule_type": "CROSS_COLUMN",
            "table": "orders",
            "columns": ["quantity", "unit_price", "line_total"],
            "conditions": [
                {
                    "type": "ARITHMETIC",
                    "target": "line_total",
                    "comparison_operator": "EQ",
                    "expression": {
                        "operator": "MULTIPLY",
                        "operands": ["quantity", "unit_price"]
                    }
                }
            ],
            "confidence": 0.95
        }

        result = map_advanced_rule_to_sql(rule)

        assert result["rule_type"] == "CROSS_COLUMN"
        assert "line_total" in result["violation_predicate"]
        assert "quantity" in result["violation_predicate"]
        assert "unit_price" in result["violation_predicate"]
        assert "<>" in result["violation_predicate"]


# =============================================================================
# TEMPORAL / TEMPORAL_ORDER Tests
# =============================================================================

class TestTemporalOrderCondition:
    """Tests cho TEMPORAL_ORDER condition compilation."""

    def test_before_operator(self):
        """Test BEFORE operator.

        Valid: left < right
        Violation: left >= right
        """
        ctx = CompileContext()
        condition = {
            "type": "TEMPORAL_ORDER",
            "left": "start_date",
            "operator": "BEFORE",
            "right": "end_date"
        }

        valid = compile_temporal_order(condition, ctx, negate=False)
        assert valid == '"start_date" < "end_date"'

        violation = compile_temporal_order(condition, ctx, negate=True)
        assert violation == '"start_date" >= "end_date"'

    def test_before_equal_operator(self):
        """Test BEFORE_EQUAL operator.

        Valid: left <= right
        Violation: left > right
        """
        ctx = CompileContext()
        condition = {
            "type": "TEMPORAL_ORDER",
            "left": "birthdate",
            "operator": "BEFORE_EQUAL",
            "right": "deathdate"
        }

        valid = compile_temporal_order(condition, ctx, negate=False)
        assert valid == '"birthdate" <= "deathdate"'

        violation = compile_temporal_order(condition, ctx, negate=True)
        assert violation == '"birthdate" > "deathdate"'

    def test_after_operator(self):
        """Test AFTER operator.

        Valid: left > right
        Violation: left <= right
        """
        ctx = CompileContext()
        condition = {
            "type": "TEMPORAL_ORDER",
            "left": "completed_at",
            "operator": "AFTER",
            "right": "started_at"
        }

        valid = compile_temporal_order(condition, ctx, negate=False)
        assert valid == '"completed_at" > "started_at"'

        violation = compile_temporal_order(condition, ctx, negate=True)
        assert violation == '"completed_at" <= "started_at"'

    def test_after_equal_operator(self):
        """Test AFTER_EQUAL operator.

        Valid: left >= right
        Violation: left < right
        """
        ctx = CompileContext()
        condition = {
            "type": "TEMPORAL_ORDER",
            "left": "approved_at",
            "operator": "AFTER_EQUAL",
            "right": "submitted_at"
        }

        valid = compile_temporal_order(condition, ctx, negate=False)
        assert valid == '"approved_at" >= "submitted_at"'

        violation = compile_temporal_order(condition, ctx, negate=True)
        assert violation == '"approved_at" < "submitted_at"'

    def test_temporal_rule_single_condition(self):
        """Test full TEMPORAL rule với single condition."""
        rule = {
            "rule_type": "TEMPORAL",
            "table": "patients",
            "columns": ["birthdate", "deathdate"],
            "conditions": [
                {
                    "type": "TEMPORAL_ORDER",
                    "left": "birthdate",
                    "operator": "BEFORE_EQUAL",
                    "right": "deathdate"
                }
            ],
            "confidence": 0.95
        }

        result = map_advanced_rule_to_sql(rule)

        assert result["rule_type"] == "TEMPORAL"
        assert '"birthdate" > "deathdate"' in result["violation_predicate"]
        assert "SELECT" in result["sql"]

    def test_temporal_rule_multiple_conditions(self):
        """Test TEMPORAL rule với nhiều temporal conditions.

        Valid: created_at <= processed_at AND processed_at <= completed_at
        Violation: created_at > processed_at OR processed_at > completed_at
        """
        rule = {
            "rule_type": "TEMPORAL",
            "table": "orders",
            "columns": ["created_at", "processed_at", "completed_at"],
            "conditions": [
                {
                    "type": "TEMPORAL_ORDER",
                    "left": "created_at",
                    "operator": "BEFORE_EQUAL",
                    "right": "processed_at"
                },
                {
                    "type": "TEMPORAL_ORDER",
                    "left": "processed_at",
                    "operator": "BEFORE_EQUAL",
                    "right": "completed_at"
                }
            ],
            "confidence": 0.9
        }

        result = map_advanced_rule_to_sql(rule)

        # Violation should have OR between negated conditions
        assert '"created_at" > "processed_at"' in result["violation_predicate"]
        assert '"processed_at" > "completed_at"' in result["violation_predicate"]
        assert " OR " in result["violation_predicate"]

    def test_mixed_temporal_operators(self):
        """Test với mixed temporal operators.

        Valid: created_at < approved_at AND approved_at <= completed_at
        Violation: NOT(created_at < approved_at) OR NOT(approved_at <= completed_at)
                = created_at >= approved_at OR approved_at > completed_at
        """
        rule = {
            "rule_type": "TEMPORAL",
            "table": "approvals",
            "columns": ["created_at", "approved_at", "completed_at"],
            "conditions": [
                {
                    "type": "TEMPORAL_ORDER",
                    "left": "created_at",
                    "operator": "BEFORE",  # <
                    "right": "approved_at"
                },
                {
                    "type": "TEMPORAL_ORDER",
                    "left": "approved_at",
                    "operator": "BEFORE_EQUAL",  # <=
                    "right": "completed_at"
                }
            ],
            "confidence": 0.85
        }

        result = map_advanced_rule_to_sql(rule)

        # NOT(BEFORE) = AFTER_EQUAL (>=)
        assert '"created_at" >= "approved_at"' in result["violation_predicate"]
        # NOT(BEFORE_EQUAL) = AFTER (>)
        assert '"approved_at" > "completed_at"' in result["violation_predicate"]


# =============================================================================
# Integration Tests - All Rule Types
# =============================================================================

class TestAllRuleTypes:
    """Integration tests cho tất cả rule types."""

    def test_cross_column_comparison_integration(self):
        """Integration: CROSS_COLUMN với COMPARISON."""
        rule = {
            "rule_type": "CROSS_COLUMN",
            "table": "patients",
            "columns": ["fips", "county"],
            "conditions": [
                {
                    "type": "COMPARISON",
                    "left": "fips",
                    "operator": "NEQ",
                    "right": {"type": "literal", "value": "99999"}  # Invalid FIPS
                }
            ]
        }
        result = map_advanced_rule_to_sql(rule)
        assert result["params"]["rule_param_1"] == "99999"

    def test_temporal_integration(self):
        """Integration: TEMPORAL với TEMPORAL_ORDER."""
        rule = {
            "rule_type": "TEMPORAL",
            "table": "encounters",
            "columns": ["start_time", "end_time"],
            "conditions": [
                {
                    "type": "TEMPORAL_ORDER",
                    "left": "start_time",
                    "operator": "BEFORE",
                    "right": "end_time"
                }
            ]
        }
        result = map_advanced_rule_to_sql(rule)
        assert "start_time" in result["sql"]
        assert "end_time" in result["sql"]


# =============================================================================
# TEMPORAL / DURATION Tests
# =============================================================================

class TestDurationCondition:
    """Tests cho DURATION condition compilation."""

    def test_duration_lte(self):
        """Test DURATION với LTE operator.

        Valid: end_time <= start_time + INTERVAL '1 DAY' * :param
        Violation: end_time > start_time + INTERVAL '1 DAY' * :param
        """
        ctx = CompileContext()
        condition = {
            "type": "DURATION",
            "start_column": "start_time",
            "end_column": "end_time",
            "operator": "LTE",
            "value": 30,
            "unit": "DAY"
        }

        valid = compile_duration(condition, ctx, negate=False)
        assert "end_time" in valid
        assert "start_time" in valid
        assert "DAY" in valid
        assert ":rule_param_1" in valid
        assert ctx.params["rule_param_1"] == 30  # Value bound to param

        violation = compile_duration(condition, ctx, negate=True)
        assert ">" in violation

    def test_duration_gt(self):
        """Test DURATION với GT operator."""
        ctx = CompileContext()
        condition = {
            "type": "DURATION",
            "start_column": "start_time",
            "end_column": "end_time",
            "operator": "GT",
            "value": 1,
            "unit": "HOUR"
        }

        result = compile_duration(condition, ctx, negate=False)
        assert "HOUR" in result
        assert ":rule_param_1" in result
        assert ctx.params["rule_param_1"] == 1

    def test_duration_minute(self):
        """Test DURATION với MINUTE unit."""
        ctx = CompileContext()
        condition = {
            "type": "DURATION",
            "start_column": "created_at",
            "end_column": "processed_at",
            "operator": "GTE",
            "value": 60,
            "unit": "MINUTE"
        }

        result = compile_duration(condition, ctx, negate=False)
        assert "MINUTE" in result
        assert "processed_at" in result
        assert "created_at" in result

    def test_duration_violation_negation(self):
        """Test negation của duration operators."""
        ctx = CompileContext()
        condition = {
            "type": "DURATION",
            "start_column": "start_date",
            "end_column": "end_date",
            "operator": "GT",
            "value": 7,
            "unit": "DAY"
        }

        valid = compile_duration(condition, ctx, negate=False)
        violation = compile_duration(condition, ctx, negate=True)

        # GT negation is LTE
        assert ">" in valid
        assert "<=" in violation

    def test_temporal_rule_with_duration(self):
        """Test full TEMPORAL rule với DURATION condition."""
        rule = {
            "rule_type": "TEMPORAL",
            "table": "encounters",
            "columns": ["start_time", "end_time"],
            "conditions": [
                {
                    "type": "DURATION",
                    "start_column": "start_time",
                    "end_column": "end_time",
                    "operator": "LTE",
                    "value": 30,
                    "unit": "DAY"
                }
            ],
            "confidence": 0.9
        }

        result = map_advanced_rule_to_sql(rule)

        assert result["rule_type"] == "TEMPORAL"
        assert "start_time" in result["sql"]
        assert "end_time" in result["sql"]
        assert "DAY" in result["violation_predicate"]


# =============================================================================
# CONDITIONAL_DEPENDENCY Tests
# =============================================================================

class TestConditionalDependency:
    """Tests cho CONDITIONAL_DEPENDENCY rule compilation."""

    def test_if_then_comparison(self):
        """Test IF-THEN với COMPARISON conditions.

        Valid: IF status='COMPLETED' THEN amount > 0
        Violation: status='COMPLETED' AND amount <= 0
        """
        rule = {
            "rule_type": "CONDITIONAL_DEPENDENCY",
            "table": "orders",
            "columns": ["status", "amount"],
            "conditions": [
                {
                    "role": "IF",
                    "type": "COMPARISON",
                    "left": "status",
                    "operator": "EQ",
                    "right": {"type": "literal", "value": "COMPLETED"}
                },
                {
                    "role": "THEN",
                    "type": "COMPARISON",
                    "left": "amount",
                    "operator": "GT",
                    "right": {"type": "literal", "value": 0}
                }
            ]
        }

        result = map_advanced_rule_to_sql(rule)

        assert result["rule_type"] == "CONDITIONAL_DEPENDENCY"
        # IF part: status = 'COMPLETED'
        assert '"status" = ' in result["violation_predicate"]
        # THEN violation: amount <= 0
        assert '"amount" <= ' in result["violation_predicate"]
        # AND between IF and THEN violation
        assert " AND " in result["violation_predicate"]

    def test_if_then_null_check(self):
        """Test IF-THEN với NULL_CHECK.

        Valid: IF gender='M' THEN maiden IS NULL
        Violation: gender='M' AND maiden IS NOT NULL
        """
        rule = {
            "rule_type": "CONDITIONAL_DEPENDENCY",
            "table": "patients",
            "columns": ["gender", "maiden"],
            "conditions": [
                {
                    "role": "IF",
                    "type": "COMPARISON",
                    "left": "gender",
                    "operator": "EQ",
                    "right": {"type": "literal", "value": "M"}
                },
                {
                    "role": "THEN",
                    "type": "NULL_CHECK",
                    "column": "maiden",
                    "operator": "IS_NULL"
                }
            ]
        }

        result = map_advanced_rule_to_sql(rule)

        # THEN violation: maiden IS NOT NULL
        assert '"maiden" IS NOT NULL' in result["violation_predicate"]

    def test_if_then_set(self):
        """Test IF-THEN với SET condition.

        Valid: IF country='US' THEN currency IN ('USD', 'USN')
        Violation: country='US' AND currency NOT IN ('USD', 'USN')
        """
        rule = {
            "rule_type": "CONDITIONAL_DEPENDENCY",
            "table": "transactions",
            "columns": ["country", "currency"],
            "conditions": [
                {
                    "role": "IF",
                    "type": "COMPARISON",
                    "left": "country",
                    "operator": "EQ",
                    "right": {"type": "literal", "value": "US"}
                },
                {
                    "role": "THEN",
                    "type": "SET",
                    "left": "currency",
                    "operator": "IN",
                    "values": ["USD", "USN"]
                }
            ]
        }

        result = map_advanced_rule_to_sql(rule)

        # THEN violation: NOT IN
        assert "NOT IN" in result["violation_predicate"]
        assert len(result["params"]) == 3  # 'US', 'USD', 'USN'

    def test_multiple_if_conditions(self):
        """Test Multiple IF conditions (AND logic).

        Valid: IF age >= 18 AND country = 'US' THEN ssn IS NOT NULL
        Violation: (age >= 18 AND country = 'US') AND ssn IS NULL
        """
        rule = {
            "rule_type": "CONDITIONAL_DEPENDENCY",
            "table": "users",
            "columns": ["age", "country", "ssn"],
            "conditions": [
                {
                    "role": "IF",
                    "type": "COMPARISON",
                    "left": "age",
                    "operator": "GTE",
                    "right": {"type": "literal", "value": 18}
                },
                {
                    "role": "IF",
                    "type": "COMPARISON",
                    "left": "country",
                    "operator": "EQ",
                    "right": {"type": "literal", "value": "US"}
                },
                {
                    "role": "THEN",
                    "type": "NULL_CHECK",
                    "column": "ssn",
                    "operator": "IS_NOT_NULL"
                }
            ]
        }

        result = map_advanced_rule_to_sql(rule)

        # Should have two IF conditions AND'd together
        assert '"age"' in result["violation_predicate"]
        assert '"country"' in result["violation_predicate"]
        assert '"ssn" IS NULL' in result["violation_predicate"]

    def test_multiple_then_conditions(self):
        """Test Multiple THEN conditions (OR logic in violation).

        Valid: IF status='COMPLETED' THEN amount > 0 AND completed_at IS NOT NULL
        Violation: status='COMPLETED' AND (amount <= 0 OR completed_at IS NULL)
        """
        rule = {
            "rule_type": "CONDITIONAL_DEPENDENCY",
            "table": "orders",
            "columns": ["status", "amount", "completed_at"],
            "conditions": [
                {
                    "role": "IF",
                    "type": "COMPARISON",
                    "left": "status",
                    "operator": "EQ",
                    "right": {"type": "literal", "value": "COMPLETED"}
                },
                {
                    "role": "THEN",
                    "type": "COMPARISON",
                    "left": "amount",
                    "operator": "GT",
                    "right": {"type": "literal", "value": 0}
                },
                {
                    "role": "THEN",
                    "type": "NULL_CHECK",
                    "column": "completed_at",
                    "operator": "IS_NOT_NULL"
                }
            ]
        }

        result = map_advanced_rule_to_sql(rule)

        # THEN violation: (amount <= 0 OR completed_at IS NULL)
        assert " OR " in result["violation_predicate"]
        assert '"amount" <= ' in result["violation_predicate"]
        assert '"completed_at" IS NULL' in result["violation_predicate"]

    def test_missing_if_condition(self):
        """Test that missing IF condition raises error."""
        rule = {
            "rule_type": "CONDITIONAL_DEPENDENCY",
            "table": "orders",
            "columns": ["amount"],
            "conditions": [
                {
                    "role": "THEN",
                    "type": "COMPARISON",
                    "left": "amount",
                    "operator": "GT",
                    "right": {"type": "literal", "value": 0}
                }
            ]
        }

        with pytest.raises(MapperError) as exc_info:
            map_advanced_rule_to_sql(rule)

        assert "IF" in str(exc_info.value)

    def test_missing_then_condition(self):
        """Test that missing THEN condition raises error."""
        rule = {
            "rule_type": "CONDITIONAL_DEPENDENCY",
            "table": "orders",
            "columns": ["status"],
            "conditions": [
                {
                    "role": "IF",
                    "type": "COMPARISON",
                    "left": "status",
                    "operator": "EQ",
                    "right": {"type": "literal", "value": "COMPLETED"}
                }
            ]
        }

        with pytest.raises(MapperError) as exc_info:
            map_advanced_rule_to_sql(rule)

        assert "THEN" in str(exc_info.value)

    def test_conditional_rule_from_generator(self):
        """Test với rule format từ generator thực tế.

        IF gender='M' THEN prefix='Mr.'
        """
        rule = {
            "rule_type": "CONDITIONAL_DEPENDENCY",
            "table": "patients",
            "columns": ["gender", "prefix"],
            "conditions": [
                {
                    "role": "IF",
                    "type": "COMPARISON",
                    "left": "gender",
                    "operator": "EQ",
                    "right": {"type": "literal", "value": "M"}
                },
                {
                    "role": "THEN",
                    "type": "COMPARISON",
                    "left": "prefix",
                    "operator": "EQ",
                    "right": {"type": "literal", "value": "Mr."}
                }
            ],
            "confidence": 0.7
        }

        result = map_advanced_rule_to_sql(rule)

        assert result["rule_type"] == "CONDITIONAL_DEPENDENCY"
        # Violation: gender='M' AND prefix<>'Mr.'
        assert '"gender" = ' in result["violation_predicate"]
        assert '"prefix" <> ' in result["violation_predicate"]
        assert result["params"]["rule_param_1"] == "M"
        assert result["params"]["rule_param_2"] == "Mr."
