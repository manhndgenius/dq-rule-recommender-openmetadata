"""Unit tests cho Temporal Generator."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.contracts.table_context import TableContext, ColumnContext, ColumnProfile
from backend.contracts.advanced_rule_router import RouterCandidate
from backend.contracts.rule_type import AdvancedRuleType
from backend.contracts.advanced_rule import GeneratorResult
from backend.engine.advanced_llm.temporal_generator import (
    TemporalGenerator,
    TemporalOutput,
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
                name="order_date",
                data_type="TIMESTAMP",
                description="Time when order was created",
                profile=ColumnProfile(null_ratio=0.0),
            ),
            ColumnContext(
                name="delivery_date",
                data_type="TIMESTAMP",
                description="Time when order was delivered",
                profile=ColumnProfile(null_ratio=0.1),
            ),
            ColumnContext(
                name="created_at",
                data_type="TIMESTAMP",
                description="Record creation time",
            ),
            ColumnContext(
                name="updated_at",
                data_type="TIMESTAMP",
                description="Record update time",
            ),
        ],
    )


class TestTemporalGenerator:
    """Tests cho TemporalGenerator."""

    @pytest.fixture
    def mock_llm_client(self):
        """Tạo mock LLM client."""
        client = MagicMock()
        client.generate_structured = AsyncMock()
        return client

    @pytest.fixture
    def generator(self, mock_llm_client):
        """Tạo generator với mock client."""
        return TemporalGenerator(mock_llm_client)

    @pytest.fixture
    def candidate(self):
        """Tạo test candidate."""
        return RouterCandidate(
            rule_type=AdvancedRuleType.TEMPORAL,
            relevant_columns=["order_date", "delivery_date"],
            confidence=0.9,
            reason="Các cột này thể hiện thứ tự thời gian.",
        )

    def test_generator_initialization(self, generator):
        """Generator nên được khởi tạo đúng."""
        assert generator is not None
        assert generator._prompt_path.name == "temporal.md"

    def test_build_generator_context(self, generator, candidate):
        """Generator nên build đúng context."""
        context = create_test_table_context()
        gen_context = generator._build_generator_context(context, candidate)

        assert "table" in gen_context
        assert gen_context["table"]["name"] == "orders"
        assert len(gen_context["columns"]) == 2
        assert gen_context["rule_type"] == "TEMPORAL"

    @pytest.mark.asyncio
    async def test_generate_returns_result(self, generator, mock_llm_client, candidate):
        """Generate nên trả về GeneratorResult."""
        context = create_test_table_context()

        mock_llm_client.generate_structured.return_value = TemporalOutput(
            rules=[
                {
                    "condition": "delivery_date >= order_date",
                    "reason": "Giao hàng không thể trước khi đặt",
                    "evidence": ["delivery_date là thời gian giao", "order_date là thời gian đặt"],
                }
            ]
        )

        result = await generator.generate(context, candidate)

        assert isinstance(result, GeneratorResult)
        assert len(result.rules) == 1
        assert "delivery_date >= order_date" == result.rules[0].condition

    @pytest.mark.asyncio
    async def test_generate_handles_empty_result(self, generator, mock_llm_client, candidate):
        """Generate nên xử lý kết quả rỗng."""
        context = create_test_table_context()

        mock_llm_client.generate_structured.return_value = TemporalOutput(rules=[])

        result = await generator.generate(context, candidate)

        assert isinstance(result, GeneratorResult)
        assert len(result.rules) == 0

    @pytest.mark.asyncio
    async def test_generate_removes_invalid_columns(self, generator, mock_llm_client):
        """Generator nên loại bỏ rules có columns không hợp lệ."""
        context = create_test_table_context()
        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.TEMPORAL,
            relevant_columns=["order_date", "nonexistent_column"],
            confidence=0.9,
            reason="Test",
        )

        mock_llm_client.generate_structured.return_value = TemporalOutput(
            rules=[
                {
                    "condition": "nonexistent_column >= order_date",
                    "reason": "Test",
                    "evidence": [],
                }
            ]
        )

        result = await generator.generate(context, candidate)

        # Candidate có column không tồn tại, nên bị loại bỏ
        assert len(result.rules) == 0

    @pytest.mark.asyncio
    async def test_generate_raises_on_llm_error(self, generator, mock_llm_client, candidate):
        """Generator nên raise GeneratorError khi LLM thất bại."""
        context = create_test_table_context()

        mock_llm_client.generate_structured.side_effect = Exception("LLM failed")

        with pytest.raises(GeneratorError):
            await generator.generate(context, candidate)
