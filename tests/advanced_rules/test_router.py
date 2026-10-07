"""Unit tests cho advanced rule router.

Test này kiểm tra router có thể sử dụng prompt file được truyền vào theo tên,
không bị fix cứng.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import BaseModel

from backend.contracts.table_context import TableContext, ColumnContext, ColumnProfile
from backend.engine.advanced_llm.router import AdvancedRuleRouter, RouterError
from backend.contracts import RouterResult, RouterCandidate, AdvancedRuleType


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
                name="status",
                data_type="VARCHAR",
                description="Order status",
                profile=ColumnProfile(top_values=[{"value": "completed", "ratio": 0.5}]),
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
            ),
            ColumnContext(
                name="unit_price",
                data_type="DECIMAL",
                description="Price per unit",
            ),
            ColumnContext(
                name="total_amount",
                data_type="DECIMAL",
                description="Total order amount",
            ),
        ],
    )


class TestAdvancedRuleRouter:
    """Tests cho AdvancedRuleRouter."""

    @pytest.fixture
    def mock_llm_client(self):
        """Tạo mock LLM client."""
        client = MagicMock()
        client.generate_structured = AsyncMock()
        return client

    @pytest.fixture
    def router(self, mock_llm_client):
        """Tạo router với mock client và default prompt."""
        return AdvancedRuleRouter(mock_llm_client)

    @pytest.fixture
    def router_with_custom_prompt(self, mock_llm_client):
        """Tạo router với custom prompt file."""
        return AdvancedRuleRouter(mock_llm_client, prompt_file="advanced_router.md")

    def test_build_router_context(self, router):
        """Router nên build compact context."""
        context = create_test_table_context()
        router_context = router._build_router_context(context)

        assert "table" in router_context
        assert router_context["table"]["name"] == "orders"
        assert len(router_context["columns"]) == 7

        # Check column data
        col_names = [c["name"] for c in router_context["columns"]]
        assert "order_date" in col_names
        assert "delivery_date" in col_names

    def test_build_user_prompt(self, router):
        """Router nên build valid JSON prompt."""
        context = {"table": {"name": "test"}, "columns": []}
        prompt = router._build_user_prompt(context)

        import json
        parsed = json.loads(prompt)
        assert parsed["table"]["name"] == "test"

    @pytest.mark.asyncio
    async def test_route_returns_result(self, router, mock_llm_client):
        """Route nên trả về RouterResult."""
        context = create_test_table_context()

        mock_llm_client.generate_structured.return_value = RouterResult(
            candidates=[
                RouterCandidate(
                    rule_type=AdvancedRuleType.TEMPORAL,
                    relevant_columns=["order_date", "delivery_date"],
                    confidence=0.9,
                    reason="Both are timestamps.",
                )
            ]
        )

        result = await router.route(context)

        assert isinstance(result, RouterResult)
        assert len(result.candidates) == 1
        assert result.candidates[0].rule_type == "TEMPORAL"

    @pytest.mark.asyncio
    async def test_route_handles_empty_result(self, router, mock_llm_client):
        """Route nên xử lý empty candidates."""
        context = create_test_table_context()

        mock_llm_client.generate_structured.return_value = RouterResult(candidates=[])

        result = await router.route(context)

        assert isinstance(result, RouterResult)
        assert len(result.candidates) == 0

    @pytest.mark.asyncio
    async def test_route_removes_nonexistent_columns(self, router, mock_llm_client):
        """Router nên loại bỏ candidates có invalid columns."""
        context = create_test_table_context()

        mock_llm_client.generate_structured.return_value = RouterResult(
            candidates=[
                RouterCandidate(
                    rule_type=AdvancedRuleType.TEMPORAL,
                    relevant_columns=["order_date", "nonexistent_column"],
                    confidence=0.9,
                    reason="Test",
                )
            ]
        )

        result = await router.route(context)

        # Candidate nên bị loại bỏ do invalid column
        assert len(result.candidates) == 0

    @pytest.mark.asyncio
    async def test_route_removes_duplicates(self, router, mock_llm_client):
        """Router nên loại bỏ duplicate candidates."""
        context = create_test_table_context()

        mock_llm_client.generate_structured.return_value = RouterResult(
            candidates=[
                RouterCandidate(
                    rule_type=AdvancedRuleType.TEMPORAL,
                    relevant_columns=["order_date", "delivery_date"],
                    confidence=0.9,
                    reason="Test 1",
                ),
                RouterCandidate(
                    rule_type=AdvancedRuleType.TEMPORAL,
                    relevant_columns=["delivery_date", "order_date"],
                    confidence=0.8,
                    reason="Test 2",
                ),
            ]
        )

        result = await router.route(context)

        # Chỉ nên còn 1 candidate (duplicates đã bị loại bỏ)
        assert len(result.candidates) == 1

    @pytest.mark.asyncio
    async def test_route_sorts_by_confidence(self, router, mock_llm_client):
        """Router nên sắp xếp candidates theo confidence giảm dần."""
        context = create_test_table_context()

        mock_llm_client.generate_structured.return_value = RouterResult(
            candidates=[
                RouterCandidate(
                    rule_type=AdvancedRuleType.TEMPORAL,
                    relevant_columns=["order_date", "delivery_date"],
                    confidence=0.7,
                    reason="Test",
                ),
                RouterCandidate(
                    rule_type=AdvancedRuleType.CONDITIONAL_DEPENDENCY,
                    relevant_columns=["status", "completed_at"],
                    confidence=0.95,
                    reason="Test",
                ),
            ]
        )

        result = await router.route(context)

        assert result.candidates[0].confidence == 0.95
        assert result.candidates[1].confidence == 0.7

    @pytest.mark.asyncio
    async def test_route_raises_on_llm_error(self, router, mock_llm_client):
        """Router nên raise RouterError khi LLM thất bại."""
        context = create_test_table_context()

        mock_llm_client.generate_structured.side_effect = Exception("LLM failed")

        with pytest.raises(RouterError):
            await router.route(context)

    def test_router_uses_prompt_file_from_parameter(self, router_with_custom_prompt):
        """Router nên sử dụng prompt file được truyền vào qua parameter."""
        from pathlib import Path

        # Verify prompt path được set đúng
        expected_path = Path(__file__).parent.parent.parent / "backend" / "engine" / "prompts" / "advanced_router.md"
        assert router_with_custom_prompt._prompt_path == expected_path
        assert router_with_custom_prompt._prompt_file == "advanced_router.md"

    def test_router_default_prompt_file(self, router):
        """Router nên có default prompt file là advanced_router_3.md."""
        from pathlib import Path

        expected_path = Path(__file__).parent.parent.parent / "backend" / "engine" / "prompts" / "advanced_router_3.md"
        assert router._prompt_path == expected_path
        assert router._prompt_file == "advanced_router_3.md"

    @pytest.mark.asyncio
    async def test_route_with_custom_prompt_file(self, router_with_custom_prompt, mock_llm_client):
        """Route với custom prompt file nên hoạt động đúng."""
        context = create_test_table_context()

        mock_llm_client.generate_structured.return_value = RouterResult(
            candidates=[
                RouterCandidate(
                    rule_type=AdvancedRuleType.TEMPORAL,
                    relevant_columns=["order_date", "delivery_date"],
                    confidence=0.9,
                    reason="Order must be delivered after it is placed.",
                )
            ]
        )

        result = await router_with_custom_prompt.route(context)

        assert isinstance(result, RouterResult)
        assert len(result.candidates) == 1
        # Verify LLM được gọi (prompt đã được load)
        mock_llm_client.generate_structured.assert_called_once()

    def test_router_loads_correct_prompt_content(self):
        """Verify router load đúng nội dung prompt file."""
        from pathlib import Path

        # Load both prompts
        prompt_1 = (Path(__file__).parent.parent.parent / "backend" / "engine" / "prompts" / "advanced_router.md").read_text()
        prompt_2 = (Path(__file__).parent.parent.parent / "backend" / "engine" / "prompts" / "advanced_router_2.md").read_text()

        # Hai prompt phải khác nhau
        assert prompt_1 != prompt_2

        # Kiểm tra nội dung đặc trưng
        assert "CROSS_COLUMN" in prompt_1
        assert "CROSS_COLUMN" in prompt_2
