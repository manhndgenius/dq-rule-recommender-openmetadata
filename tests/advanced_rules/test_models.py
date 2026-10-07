"""Unit tests cho advanced rule models."""

import pytest
from pydantic import ValidationError

from backend.contracts.rule_type import AdvancedRuleType
from backend.contracts.advanced_rule_router import RouterCandidate, RouterResult
from backend.contracts.advanced_rule import GeneratedRule, GeneratorResult


class TestAdvancedRuleType:
    """Tests cho AdvancedRuleType enum."""

    def test_rule_types_exist(self):
        """Tất cả 3 rule types nên được định nghĩa."""
        assert AdvancedRuleType.CROSS_COLUMN.value == "CROSS_COLUMN"
        assert AdvancedRuleType.CONDITIONAL_DEPENDENCY.value == "CONDITIONAL_DEPENDENCY"
        assert AdvancedRuleType.TEMPORAL.value == "TEMPORAL"

    def test_rule_types_are_strings(self):
        """Rule types nên có thể sử dụng như strings."""
        assert isinstance(AdvancedRuleType.CROSS_COLUMN, str)


class TestRouterCandidate:
    """Tests cho RouterCandidate model."""

    def test_valid_candidate(self):
        """Candidate hợp lệ nên được tạo."""
        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.TEMPORAL,
            relevant_columns=["order_date", "delivery_date"],
            confidence=0.9,
            reason="Both are timestamp columns.",
        )
        assert candidate.rule_type == "TEMPORAL"
        assert candidate.confidence == 0.9

    def test_candidate_requires_columns(self):
        """Candidate nên yêu cầu ít nhất một column."""
        with pytest.raises(ValidationError):
            RouterCandidate(
                rule_type=AdvancedRuleType.CROSS_COLUMN,
                relevant_columns=[],
                confidence=0.8,
                reason="Test",
            )

    def test_confidence_bounds(self):
        """Confidence nên nằm trong khoảng 0 và 1."""
        # Valid confidence
        RouterCandidate(
            rule_type=AdvancedRuleType.TEMPORAL,
            relevant_columns=["date"],
            confidence=0.0,
            reason="Test",
        )
        RouterCandidate(
            rule_type=AdvancedRuleType.TEMPORAL,
            relevant_columns=["date"],
            confidence=1.0,
            reason="Test",
        )

        # Invalid confidence
        with pytest.raises(ValidationError):
            RouterCandidate(
                rule_type=AdvancedRuleType.TEMPORAL,
                relevant_columns=["date"],
                confidence=1.5,
                reason="Test",
            )


class TestRouterResult:
    """Tests cho RouterResult model."""

    def test_empty_result(self):
        """Router có thể trả về danh sách rỗng."""
        result = RouterResult(candidates=[])
        assert result.candidates == []

    def test_multiple_candidates(self):
        """Router có thể trả về nhiều candidates."""
        candidates = [
            RouterCandidate(
                rule_type=AdvancedRuleType.TEMPORAL,
                relevant_columns=["date1", "date2"],
                confidence=0.9,
                reason="Test",
            ),
            RouterCandidate(
                rule_type=AdvancedRuleType.CONDITIONAL_DEPENDENCY,
                relevant_columns=["status", "completed_at"],
                confidence=0.8,
                reason="Test",
            ),
        ]
        result = RouterResult(candidates=candidates)
        assert len(result.candidates) == 2


class TestGeneratedRule:
    """Tests cho GeneratedRule model."""

    def test_valid_rule(self):
        """Generated rule hợp lệ nên được tạo."""
        rule = GeneratedRule(
            rule_type=AdvancedRuleType.TEMPORAL,
            target_table="orders",
            columns=["order_date", "delivery_date"],
            condition="delivery_date >= order_date",
            reason="Test",
            confidence=0.85,
            evidence=["order_date is creation time", "delivery_date is completion time"],
        )
        assert rule.condition == "delivery_date >= order_date"

    def test_rule_requires_columns(self):
        """Generated rule nên yêu cầu ít nhất một column."""
        with pytest.raises(ValidationError):
            GeneratedRule(
                rule_type=AdvancedRuleType.CROSS_COLUMN,
                target_table="test",
                columns=[],
                condition="test",
                reason="Test",
            )

    def test_default_confidence(self):
        """Generated rule nên có confidence mặc định."""
        rule = GeneratedRule(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            target_table="test",
            columns=["col1", "col2"],
            condition="test",
            reason="Test",
        )
        assert rule.confidence == 0.8


class TestGeneratorResult:
    """Tests cho GeneratorResult model."""

    def test_empty_result(self):
        """Generator có thể trả về danh sách rỗng."""
        result = GeneratorResult(rules=[])
        assert result.rules == []

    def test_multiple_rules(self):
        """Generator có thể trả về nhiều rules."""
        rules = [
            GeneratedRule(
                rule_type=AdvancedRuleType.TEMPORAL,
                target_table="orders",
                columns=["date1", "date2"],
                condition="date2 >= date1",
                reason="Test",
            ),
            GeneratedRule(
                rule_type=AdvancedRuleType.CROSS_COLUMN,
                target_table="orders",
                columns=["qty", "price", "total"],
                condition="total = qty * price",
                reason="Test",
            ),
        ]
        result = GeneratorResult(rules=rules)
        assert len(result.rules) == 2
