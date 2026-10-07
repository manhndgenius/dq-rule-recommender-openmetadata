"""Unit tests cho Conditional Dependency Generator."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.contracts.table_context import TableContext, ColumnContext, ColumnProfile
from backend.contracts.advanced_rule_router import RouterCandidate
from backend.contracts.rule_type import AdvancedRuleType
from backend.contracts.advanced_rule import GeneratorResult
from backend.engine.advanced_llm.conditional_dependency_generator import (
    ConditionalDependencyGenerator,
    ConditionalDependencyOutput,
)
from backend.engine.advanced_llm.cross_column_generator import GeneratorError


def create_test_table_context() -> TableContext:
    """Tạo test table context."""
    return TableContext(
        database_name="test_db",
        schema_name="public",
        table_name="orders",
        table_description="Customer orders table",
        columns=[
            ColumnContext(
                name="status",
                data_type="VARCHAR",
                description="Order status",
                profile=ColumnProfile(
                    top_values=[
                        {"value": "completed", "ratio": 0.5},
                        {"value": "pending", "ratio": 0.3},
                    ]
                ),
            ),
            ColumnContext(
                name="completed_at",
                data_type="TIMESTAMP",
                nullable=True,
                description="Time when order was completed",
            ),
            ColumnContext(
                name="payment_method",
                data_type="VARCHAR",
                description="Payment method",
            ),
            ColumnContext(
                name="transaction_id",
                data_type="VARCHAR",
                nullable=True,
                description="Payment transaction ID",
            ),
        ],
    )


class TestConditionalDependencyGenerator:
    """Tests cho ConditionalDependencyGenerator."""

    @pytest.fixture
    def mock_llm_client(self):
        """Tạo mock LLM client."""
        client = MagicMock()
        client.generate_structured = AsyncMock()
        return client

    @pytest.fixture
    def generator(self, mock_llm_client):
        """Tạo generator với mock client."""
        return ConditionalDependencyGenerator(mock_llm_client)

    @pytest.fixture
    def candidate(self):
        """Tạo test candidate."""
        return RouterCandidate(
            rule_type=AdvancedRuleType.CONDITIONAL_DEPENDENCY,
            relevant_columns=["status", "completed_at"],
            confidence=0.9,
            reason="Status completed có thể yêu cầu completed_at.",
        )

    def test_generator_initialization(self, generator):
        """Generator nên được khởi tạo đúng."""
        assert generator is not None
        assert generator._prompt_path.name == "conditional_dependency.md"

    def test_build_generator_context(self, generator, candidate):
        """Generator nên build đúng context."""
        context = create_test_table_context()
        gen_context = generator._build_generator_context(context, candidate)

        assert "table" in gen_context
        assert gen_context["table"]["name"] == "orders"
        assert len(gen_context["columns"]) == 2
        assert gen_context["rule_type"] == "CONDITIONAL_DEPENDENCY"

    @pytest.mark.asyncio
    async def test_generate_returns_result(self, generator, mock_llm_client, candidate):
        """Generate nên trả về GeneratorResult."""
        context = create_test_table_context()

        mock_llm_client.generate_structured.return_value = ConditionalDependencyOutput(
            rules=[
                {
                    "condition": "IF status = 'completed' THEN completed_at IS NOT NULL",
                    "reason": "Đơn hàng completed cần có thời gian hoàn thành",
                    "evidence": ["status là completed", "completed_at là timestamp"],
                }
            ]
        )

        result = await generator.generate(context, candidate)

        assert isinstance(result, GeneratorResult)
        assert len(result.rules) == 1
        assert "completed_at IS NOT NULL" in result.rules[0].condition

    @pytest.mark.asyncio
    async def test_generate_handles_empty_result(self, generator, mock_llm_client, candidate):
        """Generate nên xử lý kết quả rỗng."""
        context = create_test_table_context()

        mock_llm_client.generate_structured.return_value = ConditionalDependencyOutput(rules=[])

        result = await generator.generate(context, candidate)

        assert isinstance(result, GeneratorResult)
        assert len(result.rules) == 0

    @pytest.mark.asyncio
    async def test_generate_raises_on_llm_error(self, generator, mock_llm_client, candidate):
        """Generator nên raise GeneratorError khi LLM thất bại."""
        context = create_test_table_context()

        mock_llm_client.generate_structured.side_effect = Exception("LLM failed")

        with pytest.raises(GeneratorError):
            await generator.generate(context, candidate)
