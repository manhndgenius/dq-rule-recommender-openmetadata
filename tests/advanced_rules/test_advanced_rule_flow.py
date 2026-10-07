"""Integration test cho advanced rule flow (mocked LLM)."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.contracts.table_context import TableContext, ColumnContext, ColumnProfile
from backend.engine.advanced_rule_service import AdvancedRuleService
from backend.engine.advanced_llm import (
    LLMClient,
    RouterResult,
    RouterCandidate,
    GeneratedRule,
    AdvancedRuleType,
)
from backend.engine.advanced_llm.cross_column_generator import CrossColumnOutput
from backend.engine.advanced_llm.temporal_generator import TemporalOutput
from backend.engine.advanced_llm.conditional_dependency_generator import ConditionalDependencyOutput


def create_orders_table_context() -> TableContext:
    """Tạo test table context cho orders table."""
    return TableContext(
        database_name="test_db",
        schema_name="public",
        table_name="orders",
        table_description="Customer orders table",
        columns=[
            ColumnContext(
                name="order_id",
                data_type="INTEGER",
                description="Order ID",
            ),
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
                name="quantity",
                data_type="INTEGER",
                description="Number of items",
                profile=ColumnProfile(null_ratio=0.0),
            ),
            ColumnContext(
                name="unit_price",
                data_type="DECIMAL",
                description="Price per unit",
                profile=ColumnProfile(null_ratio=0.0),
            ),
            ColumnContext(
                name="total_amount",
                data_type="DECIMAL",
                description="Total order amount",
                profile=ColumnProfile(null_ratio=0.1),
            ),
        ],
    )


class MockLLMClient:
    """Mock LLM client cho integration test.

    Mock này track candidate đang được xử lý và trả về
    output model phù hợp với response_model type.
    """

    def __init__(self, router_response, generator_responses):
        self._router_response = router_response
        self._generator_responses = generator_responses
        self._call_count = 0

    async def generate_structured(self, system_prompt, user_prompt, response_model):
        self._call_count += 1

        # First call is router - return RouterResult
        if self._call_count == 1:
            return self._router_response

        # Subsequent calls are generators - return correct output model
        idx = self._call_count - 2
        if idx < len(self._generator_responses):
            return self._generator_responses[idx]

        return response_model()


class TestAdvancedRuleFlow:
    """Integration tests cho full advanced rule flow."""

    @pytest.mark.asyncio
    async def test_full_flow_temporal(self):
        """Test flow với temporal candidate."""
        context = create_orders_table_context()

        # Mock router trả về TEMPORAL candidate
        router_response = RouterResult(
            candidates=[
                RouterCandidate(
                    rule_type=AdvancedRuleType.TEMPORAL,
                    relevant_columns=["order_date", "delivery_date"],
                    confidence=0.93,
                    reason="Cả hai đều là timestamps thể hiện lifecycle.",
                )
            ]
        )

        # Mock generator trả về temporal rule (dùng TemporalOutput)
        generator_response = TemporalOutput(
            rules=[
                {
                    "condition": "delivery_date >= order_date",
                    "reason": "Giao hàng không thể trước khi đặt.",
                    "evidence": ["order_date là thời gian tạo", "delivery_date là thời gian giao"],
                }
            ]
        )

        mock_client = MockLLMClient(router_response, [generator_response])
        service = AdvancedRuleService(llm_client=mock_client, min_confidence=0.75)

        router_result, rules = await service.recommend(context)

        # Verify router result
        assert len(router_result.candidates) == 1
        assert router_result.candidates[0].rule_type == "TEMPORAL"

        # Verify generated rules
        assert len(rules) == 1
        assert rules[0].condition == "delivery_date >= order_date"

    @pytest.mark.asyncio
    async def test_full_flow_multiple_candidates(self):
        """Test flow với nhiều candidates."""
        context = create_orders_table_context()

        # Mock router trả về nhiều candidates
        router_response = RouterResult(
            candidates=[
                RouterCandidate(
                    rule_type=AdvancedRuleType.TEMPORAL,
                    relevant_columns=["order_date", "delivery_date"],
                    confidence=0.93,
                    reason="Timestamps.",
                ),
                RouterCandidate(
                    rule_type=AdvancedRuleType.CONDITIONAL_DEPENDENCY,
                    relevant_columns=["status", "completed_at"],
                    confidence=0.86,
                    reason="Status completed.",
                ),
                RouterCandidate(
                    rule_type=AdvancedRuleType.CROSS_COLUMN,
                    relevant_columns=["quantity", "unit_price", "total_amount"],
                    confidence=0.78,
                    reason="Có thể tính toán.",
                ),
            ]
        )

        # Mock generators responses (dùng đúng output models)
        generator_responses = [
            TemporalOutput(rules=[
                {
                    "condition": "delivery_date >= order_date",
                    "reason": "Test",
                    "evidence": [],
                }
            ]),
            ConditionalDependencyOutput(rules=[
                {
                    "condition": "IF status = 'completed' THEN completed_at IS NOT NULL",
                    "reason": "Test",
                    "evidence": [],
                }
            ]),
            CrossColumnOutput(rules=[
                {
                    "condition": "total_amount = quantity * unit_price",
                    "reason": "Test",
                    "evidence": [],
                }
            ]),
        ]

        mock_client = MockLLMClient(router_response, generator_responses)
        service = AdvancedRuleService(llm_client=mock_client, min_confidence=0.75)

        router_result, rules = await service.recommend(context)

        # Verify
        assert len(router_result.candidates) == 3
        assert len(rules) == 3

    @pytest.mark.asyncio
    async def test_empty_candidates(self):
        """Test khi router không tìm thấy candidates."""
        context = create_orders_table_context()

        router_response = RouterResult(candidates=[])
        mock_client = MockLLMClient(router_response, [])
        service = AdvancedRuleService(llm_client=mock_client, min_confidence=0.75)

        router_result, rules = await service.recommend(context)

        assert len(router_result.candidates) == 0
        assert len(rules) == 0

    @pytest.mark.asyncio
    async def test_confidence_threshold_filtering(self):
        """Test confidence threshold filtering."""
        context = create_orders_table_context()

        router_response = RouterResult(
            candidates=[
                RouterCandidate(
                    rule_type=AdvancedRuleType.TEMPORAL,
                    relevant_columns=["order_date", "delivery_date"],
                    confidence=0.9,  # Trên threshold
                    reason="Test",
                ),
                RouterCandidate(
                    rule_type=AdvancedRuleType.CROSS_COLUMN,
                    relevant_columns=["quantity", "total_amount"],
                    confidence=0.5,  # Dưới threshold
                    reason="Test",
                ),
            ]
        )

        generator_response = TemporalOutput(rules=[
            {
                "condition": "delivery_date >= order_date",
                "reason": "Test",
                "evidence": [],
            }
        ])

        mock_client = MockLLMClient(router_response, [generator_response])
        service = AdvancedRuleService(llm_client=mock_client, min_confidence=0.75)

        router_result, rules = await service.recommend(context)

        # Chỉ có 1 candidate được chọn (confidence 0.9)
        # CROSS_COLUMN candidate (0.5) bị filter out
        assert len(router_result.candidates) == 2
        assert len(rules) == 1
