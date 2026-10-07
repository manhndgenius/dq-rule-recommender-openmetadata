"""Unit tests cho Cross-Column Generator.

Test này kiểm tra việc generate CROSS_COLUMN condition từ:
- Router đã cung cấp: columns + reason
- Generator cần tạo: condition cụ thể
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.contracts.table_context import TableContext, ColumnContext, ColumnProfile
from backend.contracts.advanced_rule_router import RouterCandidate
from backend.contracts.rule_type import AdvancedRuleType
from backend.contracts.advanced_rule import GeneratorResult
from backend.engine.advanced_llm.cross_column_generator import (
    CrossColumnGenerator,
    CrossColumnOutput,
    GeneratorError,
)


def create_test_table_context() -> TableContext:
    """Tạo test table context cho bảng orders."""
    return TableContext(
        database_name="test_db",
        schema_name="public",
        table_name="orders",
        table_description="Customer orders table",
        columns=[
            ColumnContext(
                name="quantity",
                data_type="INTEGER",
                description="Number of items ordered",
                profile=ColumnProfile(null_ratio=0.0, min_value=1, max_value=100),
            ),
            ColumnContext(
                name="unit_price",
                data_type="DECIMAL",
                description="Price per unit in USD",
                profile=ColumnProfile(null_ratio=0.0, min_value=0.01, max_value=999.99),
            ),
            ColumnContext(
                name="total_amount",
                data_type="DECIMAL",
                description="Total order amount",
                profile=ColumnProfile(null_ratio=0.0, min_value=0.01, max_value=99999.99),
            ),
            ColumnContext(
                name="discount_amount",
                data_type="DECIMAL",
                description="Discount applied to order",
                profile=ColumnProfile(null_ratio=0.3, min_value=0.0, max_value=1000.0),
            ),
        ],
    )


def create_healthcare_table_context() -> TableContext:
    """Tạo test table context cho bảng patients (tương tự real data)."""
    return TableContext(
        database_name="HealthCare",
        schema_name="public",
        table_name="patients",
        table_description="Patient demographics and healthcare information",
        columns=[
            ColumnContext(
                name="healthcare_coverage",
                data_type="DECIMAL",
                description="Insurance coverage amount",
                profile=ColumnProfile(null_ratio=0.15, min_value=0, max_value=500000),
            ),
            ColumnContext(
                name="healthcare_expenses",
                data_type="DECIMAL",
                description="Total healthcare expenses",
                profile=ColumnProfile(null_ratio=0.05, min_value=0, max_value=1000000),
            ),
        ],
    )


def create_geography_table_context() -> TableContext:
    """Tạo test table context cho geographic data."""
    return TableContext(
        database_name="GeoDB",
        schema_name="public",
        table_name="locations",
        table_description="Geographic location data",
        columns=[
            ColumnContext(
                name="fips",
                data_type="VARCHAR",
                description="FIPS county code",
                profile=ColumnProfile(null_ratio=0.0),
            ),
            ColumnContext(
                name="county",
                data_type="VARCHAR",
                description="County name",
                profile=ColumnProfile(null_ratio=0.0),
            ),
            ColumnContext(
                name="state",
                data_type="VARCHAR",
                description="State abbreviation",
                profile=ColumnProfile(null_ratio=0.0),
            ),
            ColumnContext(
                name="zip",
                data_type="VARCHAR",
                description="ZIP code",
                profile=ColumnProfile(null_ratio=0.0),
            ),
            ColumnContext(
                name="city",
                data_type="VARCHAR",
                description="City name",
                profile=ColumnProfile(null_ratio=0.0),
            ),
        ],
    )


class TestCrossColumnGeneratorContextBuilding:
    """Tests cho việc build context từ router candidate."""

    @pytest.fixture
    def mock_llm_client(self):
        """Tạo mock LLM client."""
        client = MagicMock()
        client.generate_structured = AsyncMock()
        return client

    @pytest.fixture
    def generator(self, mock_llm_client):
        """Tạo generator với mock client."""
        return CrossColumnGenerator(mock_llm_client)

    def test_build_context_includes_reason_from_router(self, generator):
        """Context phải bao gồm reason từ router candidate."""
        context = create_test_table_context()
        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["quantity", "unit_price", "total_amount"],
            confidence=0.9,
            reason="These columns have a mathematical relationship: total = quantity * unit_price",
        )

        gen_context = generator._build_generator_context(context, candidate)

        # Verify reason được include
        assert "reason" in gen_context
        assert gen_context["reason"] == "These columns have a mathematical relationship: total = quantity * unit_price"

    def test_build_context_includes_only_relevant_columns(self, generator):
        """Context chỉ bao gồm columns được router chọn."""
        context = create_test_table_context()
        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["quantity", "unit_price"],
            confidence=0.9,
            reason="Price calculation columns",
        )

        gen_context = generator._build_generator_context(context, candidate)

        # Chỉ 2 columns được include
        assert len(gen_context["columns"]) == 2
        col_names = [c["name"] for c in gen_context["columns"]]
        assert "quantity" in col_names
        assert "unit_price" in col_names
        assert "total_amount" not in col_names

    def test_build_context_includes_column_metadata(self, generator):
        """Context bao gồm metadata của columns (datatype, description, profiling)."""
        context = create_test_table_context()
        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["quantity", "unit_price"],
            confidence=0.9,
            reason="Price columns",
        )

        gen_context = generator._build_generator_context(context, candidate)

        quantity_col = next(c for c in gen_context["columns"] if c["name"] == "quantity")
        assert quantity_col["datatype"] == "INTEGER"
        assert quantity_col["description"] == "Number of items ordered"
        assert "profiling" in quantity_col


class TestCrossColumnConditionGeneration:
    """Tests cho việc generate condition từ router output."""

    @pytest.fixture
    def mock_llm_client(self):
        """Tạo mock LLM client."""
        client = MagicMock()
        client.generate_structured = AsyncMock()
        return client

    @pytest.fixture
    def generator(self, mock_llm_client):
        """Tạo generator với mock client."""
        return CrossColumnGenerator(mock_llm_client)

    @pytest.mark.asyncio
    async def test_generate_mathematical_condition(
        self, generator, mock_llm_client
    ):
        """Test generate mathematical condition: total = quantity * unit_price."""
        context = create_test_table_context()

        # Router đã cung cấp columns + reason
        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["quantity", "unit_price", "total_amount"],
            confidence=0.9,
            reason="Total amount should equal quantity multiplied by unit price",
        )

        # Mock LLM trả về condition cụ thể
        mock_llm_client.generate_structured.return_value = CrossColumnOutput(
            rules=[
                {
                    "condition": "total_amount = quantity * unit_price",
                    "reason": "Mathematical calculation: total = qty * price",
                    "evidence": [
                        "quantity is INTEGER for item count",
                        "unit_price is DECIMAL for price",
                        "total_amount is the result column",
                    ],
                }
            ]
        )

        result = await generator.generate(context, candidate)

        assert isinstance(result, GeneratorResult)
        assert len(result.rules) == 1

        rule = result.rules[0]
        assert rule.condition == "total_amount = quantity * unit_price"
        assert rule.columns == ["quantity", "unit_price", "total_amount"]
        assert rule.rule_type == AdvancedRuleType.CROSS_COLUMN
        assert rule.target_table == "orders"

    @pytest.mark.asyncio
    async def test_generate_comparison_condition(
        self, generator, mock_llm_client
    ):
        """Test generate comparison condition: discount <= total_amount."""
        context = create_test_table_context()

        # Router đã cung cấp columns + reason
        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["discount_amount", "total_amount"],
            confidence=0.85,
            reason="Discount should not exceed the total order amount",
        )

        # Mock LLM trả về comparison condition
        mock_llm_client.generate_structured.return_value = CrossColumnOutput(
            rules=[
                {
                    "condition": "discount_amount <= total_amount",
                    "reason": "Discount cannot be greater than the order total",
                    "evidence": [
                        "discount_amount represents the discount value",
                        "total_amount is the order total",
                        "Business rule: discount <= total",
                    ],
                }
            ]
        )

        result = await generator.generate(context, candidate)

        assert len(result.rules) == 1
        assert result.rules[0].condition == "discount_amount <= total_amount"

    @pytest.mark.asyncio
    async def test_generate_healthcare_coverage_condition(
        self, generator, mock_llm_client
    ):
        """Test generate healthcare coverage condition từ real scenario."""
        context = create_healthcare_table_context()

        # Router đã cung cấp columns + reason (từ real run)
        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["healthcare_coverage", "healthcare_expenses"],
            confidence=0.85,
            reason="Coverage amount represents the insured portion of total healthcare expenses, implying a direct financial relationship",
        )

        # Mock LLM trả về condition
        mock_llm_client.generate_structured.return_value = CrossColumnOutput(
            rules=[
                {
                    "condition": "healthcare_coverage <= healthcare_expenses",
                    "reason": "Insurance coverage should not exceed total healthcare expenses",
                    "evidence": [
                        "healthcare_coverage: Insurance coverage amount",
                        "healthcare_expenses: Total healthcare expenses",
                        "Business logic: coverage is a subset of expenses",
                    ],
                }
            ]
        )

        result = await generator.generate(context, candidate)

        assert len(result.rules) == 1
        rule = result.rules[0]
        assert rule.condition == "healthcare_coverage <= healthcare_expenses"
        assert rule.columns == ["healthcare_coverage", "healthcare_expenses"]
        assert rule.target_table == "patients"

    @pytest.mark.asyncio
    async def test_generate_aggregation_condition(self, generator, mock_llm_client):
        """Test generate aggregation condition: net = gross - discount."""
        context = create_test_table_context()

        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["discount_amount", "total_amount"],
            confidence=0.8,
            reason="Net amount after discount can be derived from total minus discount",
        )

        mock_llm_client.generate_structured.return_value = CrossColumnOutput(
            rules=[
                {
                    "condition": "total_amount >= discount_amount",
                    "reason": "Total must be greater than or equal to discount",
                    "evidence": [
                        "discount_amount cannot exceed total",
                        "Logical constraint for valid discount",
                    ],
                }
            ]
        )

        result = await generator.generate(context, candidate)

        assert len(result.rules) == 1
        assert ">=" in result.rules[0].condition

    @pytest.mark.asyncio
    async def test_generate_multiple_rules_from_single_candidate(
        self, generator, mock_llm_client
    ):
        """Test generate nhiều rules từ một candidate."""
        context = create_test_table_context()

        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["quantity", "unit_price", "total_amount", "discount_amount"],
            confidence=0.9,
            reason="Order calculation columns",
        )

        # Mock LLM trả về nhiều rules
        mock_llm_client.generate_structured.return_value = CrossColumnOutput(
            rules=[
                {
                    "condition": "total_amount = quantity * unit_price",
                    "reason": "Total calculation",
                    "evidence": [],
                },
                {
                    "condition": "discount_amount <= total_amount",
                    "reason": "Discount constraint",
                    "evidence": [],
                },
            ]
        )

        result = await generator.generate(context, candidate)

        assert len(result.rules) == 2
        conditions = [r.condition for r in result.rules]
        assert "total_amount = quantity * unit_price" in conditions
        assert "discount_amount <= total_amount" in conditions

    @pytest.mark.asyncio
    async def test_generate_empty_when_no_valid_rules(
        self, generator, mock_llm_client
    ):
        """Test generate trả về empty khi không có valid rules."""
        context = create_test_table_context()

        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["quantity", "unit_price"],
            confidence=0.9,
            reason="Some reason",
        )

        mock_llm_client.generate_structured.return_value = CrossColumnOutput(rules=[])

        result = await generator.generate(context, candidate)

        assert isinstance(result, GeneratorResult)
        assert len(result.rules) == 0


class TestCrossColumnValidation:
    """Tests cho validation rules."""

    @pytest.fixture
    def mock_llm_client(self):
        """Tạo mock LLM client."""
        client = MagicMock()
        client.generate_structured = AsyncMock()
        return client

    @pytest.fixture
    def generator(self, mock_llm_client):
        """Tạo generator với mock client."""
        return CrossColumnGenerator(mock_llm_client)

    @pytest.mark.asyncio
    async def test_removes_invalid_columns(self, generator, mock_llm_client):
        """Loại bỏ rules có columns không tồn tại trong table."""
        context = create_test_table_context()

        # Candidate với column không tồn tại
        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["quantity", "nonexistent_column"],
            confidence=0.9,
            reason="Test",
        )

        # LLM tạo rule với column không hợp lệ
        mock_llm_client.generate_structured.return_value = CrossColumnOutput(
            rules=[
                {
                    "condition": "test = quantity + nonexistent_column",
                    "reason": "Test rule",
                    "evidence": [],
                }
            ]
        )

        result = await generator.generate(context, candidate)

        # Rule với nonexistent_column bị loại
        assert len(result.rules) == 0

    @pytest.mark.asyncio
    async def test_removes_duplicate_conditions(self, generator, mock_llm_client):
        """Loại bỏ duplicate rules."""
        context = create_test_table_context()

        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["quantity", "unit_price", "total_amount"],
            confidence=0.9,
            reason="Calculation columns",
        )

        # LLM trả về duplicate rules
        mock_llm_client.generate_structured.return_value = CrossColumnOutput(
            rules=[
                {
                    "condition": "total_amount = quantity * unit_price",
                    "reason": "Rule 1",
                    "evidence": [],
                },
                {
                    "condition": "total_amount = quantity * unit_price",
                    "reason": "Rule 2 (duplicate)",
                    "evidence": [],
                },
            ]
        )

        result = await generator.generate(context, candidate)

        # Chỉ còn 1 rule
        assert len(result.rules) == 1

    @pytest.mark.asyncio
    async def test_removes_empty_condition(self, generator, mock_llm_client):
        """Loại bỏ rules có condition rỗng."""
        context = create_test_table_context()

        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["quantity", "total_amount"],
            confidence=0.9,
            reason="Test",
        )

        mock_llm_client.generate_structured.return_value = CrossColumnOutput(
            rules=[
                {
                    "condition": "",
                    "reason": "Empty condition",
                    "evidence": [],
                },
                {
                    "condition": "total_amount >= quantity",
                    "reason": "Valid condition",
                    "evidence": [],
                },
            ]
        )

        result = await generator.generate(context, candidate)

        assert len(result.rules) == 1
        assert result.rules[0].condition == "total_amount >= quantity"

    @pytest.mark.asyncio
    async def test_raises_error_on_llm_failure(self, generator, mock_llm_client):
        """Raise GeneratorError khi LLM thất bại."""
        context = create_test_table_context()

        candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["quantity", "total_amount"],
            confidence=0.9,
            reason="Test",
        )

        mock_llm_client.generate_structured.side_effect = Exception("LLM API Error")

        with pytest.raises(GeneratorError) as exc_info:
            await generator.generate(context, candidate)

        assert "LLM API Error" in str(exc_info.value)


class TestCrossColumnEndToEnd:
    """End-to-end tests mô phỏng real scenario."""

    @pytest.fixture
    def mock_llm_client(self):
        """Tạo mock LLM client."""
        client = MagicMock()
        client.generate_structured = AsyncMock()
        return client

    @pytest.fixture
    def generator(self, mock_llm_client):
        """Tạo generator với mock client."""
        return CrossColumnGenerator(mock_llm_client)

    @pytest.mark.asyncio
    async def test_real_router_output_scenario(self, generator, mock_llm_client):
        """Test với router output thực tế từ doc/report.

        Router output:
        {
          "rule_type": "CROSS_COLUMN",
          "relevant_columns": ["healthcare_coverage", "healthcare_expenses"],
          "confidence": 0.85,
          "reason": "Coverage amount represents the insured portion of total
                     healthcare expenses, implying a direct financial relationship."
        }

        Expected generator output:
        {
          "condition": "healthcare_coverage <= healthcare_expenses",
          "reason": "...",
          "evidence": [...]
        }
        """
        context = create_healthcare_table_context()

        # Router output (từ real run trong doc)
        router_candidate = RouterCandidate(
            rule_type=AdvancedRuleType.CROSS_COLUMN,
            relevant_columns=["healthcare_coverage", "healthcare_expenses"],
            confidence=0.85,
            reason="Coverage amount represents the insured portion of total healthcare expenses, implying a direct financial relationship",
        )

        # Generator tạo condition cụ thể
        mock_llm_client.generate_structured.return_value = CrossColumnOutput(
            rules=[
                {
                    "condition": "healthcare_coverage <= healthcare_expenses",
                    "reason": "Insurance coverage should not exceed total healthcare expenses - coverage is the insured portion of total expenses",
                    "evidence": [
                        "healthcare_coverage: Insurance coverage amount in USD",
                        "healthcare_expenses: Total healthcare expenses in USD",
                        "Business logic: coverage is a subset/part of expenses",
                        "Financial constraint: what is covered cannot exceed total cost",
                    ],
                }
            ]
        )

        result = await generator.generate(context, router_candidate)

        # Verify
        assert len(result.rules) == 1
        rule = result.rules[0]

        # Condition cụ thể được generate
        assert rule.condition == "healthcare_coverage <= healthcare_expenses"

        # Columns được preserve từ router
        assert set(rule.columns) == {"healthcare_coverage", "healthcare_expenses"}

        # Confidence được điều chỉnh
        assert rule.confidence <= 0.9  # max 0.9 for generators

        # Target table
        assert rule.target_table == "patients"

        # Evidence từ LLM
        assert len(rule.evidence) > 0
        assert any("coverage" in str(e).lower() for e in rule.evidence)

    @pytest.mark.asyncio
    async def test_multiple_cross_column_candidates(self, generator, mock_llm_client):
        """Test nhiều CROSS_COLUMN candidates như real pipeline."""
        context = create_geography_table_context()

        # 2 router candidates khác nhau
        candidates = [
            RouterCandidate(
                rule_type=AdvancedRuleType.CROSS_COLUMN,
                relevant_columns=["fips", "county"],
                confidence=0.9,
                reason="FIPS codes are standard geographic identifiers for counties; they should correspond to county names",
            ),
            RouterCandidate(
                rule_type=AdvancedRuleType.CROSS_COLUMN,
                relevant_columns=["state", "zip", "city"],
                confidence=0.8,
                reason="ZIP codes are designed to associate with specific city and state locations",
            ),
        ]

        # Mock returns cho từng call
        mock_llm_client.generate_structured.side_effect = [
            CrossColumnOutput(
                rules=[
                    {
                        "condition": "fips IS NOT NULL AND county IS NOT NULL",
                        "reason": "Both FIPS and county should be present together",
                        "evidence": ["FIPS is the identifier for county", "county name depends on FIPS"],
                    }
                ]
            ),
            CrossColumnOutput(
                rules=[
                    {
                        "condition": "zip IS NOT NULL",
                        "reason": "ZIP code links city and state",
                        "evidence": ["ZIP is the postal code", "links location data"],
                    }
                ]
            ),
        ]

        # Generate cho từng candidate
        all_rules = []
        for candidate in candidates:
            result = await generator.generate(context, candidate)
            all_rules.extend(result.rules)

        # Tổng cộng 2 rules
        assert len(all_rules) == 2

        # Verify columns khác nhau
        cols_sets = [set(r.columns) for r in all_rules]
        assert {"fips", "county"} in cols_sets
        assert {"state", "zip", "city"} in cols_sets
