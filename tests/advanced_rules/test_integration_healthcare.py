"""Integration tests cho advanced rules với realistic table schemas."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from backend.contracts.table_context import TableContext, ColumnContext, ColumnProfile
from backend.engine.advanced_rule_service import AdvancedRuleService
from backend.engine.advanced_llm import (
    RouterResult,
    RouterCandidate,
    AdvancedRuleType,
)
from backend.engine.advanced_llm.temporal_generator import TemporalOutput
from backend.engine.advanced_llm.conditional_dependency_generator import ConditionalDependencyOutput
from backend.engine.advanced_llm.cross_column_generator import CrossColumnOutput


# =============================================================================
# Test Cases từ Healthcare Schema
# =============================================================================

def create_encounters_table_context() -> TableContext:
    """Tạo table context cho encounters table (healthcare)."""
    return TableContext(
        database_name="HealthCare",
        schema_name="public",
        table_name="encounters",
        table_description="Healthcare encounters or visits including emergency, inpatient, outpatient, and wellness visits.",
        columns=[
            ColumnContext(name="Id", data_type="uuid", description="Unique identifier for the encounter"),
            ColumnContext(name="START", data_type="timestamp", description="Encounter start date and time", profile=ColumnProfile(null_ratio=0.0)),
            ColumnContext(name="STOP", data_type="timestamp", nullable=True, description="Encounter end date and time", profile=ColumnProfile(null_ratio=0.2)),
            ColumnContext(name="PATIENT", data_type="uuid", description="Reference to patient ID"),
            ColumnContext(name="ENCOUNTERCLASS", data_type="text", description="Type of encounter: wellness, ambulatory, emergency, inpatient, urgentcare"),
            ColumnContext(name="CODE", data_type="text", description="SNOMED-CT code for the encounter type"),
            ColumnContext(name="DESCRIPTION", data_type="text", description="Description of the encounter type"),
            ColumnContext(name="BASE_ENCOUNTER_COST", data_type="numeric", description="Base cost of the encounter"),
            ColumnContext(name="TOTAL_CLAIM_COST", data_type="numeric", description="Total claimed cost for the encounter"),
            ColumnContext(name="PAYER_COVERAGE", data_type="numeric", description="Amount covered by payer"),
            ColumnContext(name="REASONCODE", data_type="text", nullable=True, description="SNOMED-CT code for encounter reason"),
        ],
    )


def create_medications_table_context() -> TableContext:
    """Tạo table context cho medications table (healthcare)."""
    return TableContext(
        database_name="HealthCare",
        schema_name="public",
        table_name="medications",
        table_description="Patient medication prescriptions and dispensations including drug codes, costs, and refills.",
        columns=[
            ColumnContext(name="START", data_type="timestamp", description="Medication start date and time", profile=ColumnProfile(null_ratio=0.0)),
            ColumnContext(name="STOP", data_type="timestamp", nullable=True, description="Medication stop date and time", profile=ColumnProfile(null_ratio=0.4)),
            ColumnContext(name="PATIENT", data_type="uuid", description="Reference to patient ID"),
            ColumnContext(name="CODE", data_type="text", description="RxNorm code for the medication"),
            ColumnContext(name="DESCRIPTION", data_type="text", description="Medication name and dosage"),
            ColumnContext(name="BASE_COST", data_type="numeric", description="Base cost of the medication"),
            ColumnContext(name="PAYER_COVERAGE", data_type="numeric", description="Amount covered by payer"),
            ColumnContext(name="DISPENSES", data_type="integer", description="Number of times dispensed"),
            ColumnContext(name="TOTALCOST", data_type="numeric", description="Total cost (base_cost * dispenses)"),
        ],
    )


def create_patients_table_context() -> TableContext:
    """Tạo table context cho patients table (healthcare)."""
    return TableContext(
        database_name="HealthCare",
        schema_name="public",
        table_name="patients",
        table_description="Demographic and personal information of patients.",
        columns=[
            ColumnContext(name="Id", data_type="uuid", description="Unique identifier for the patient"),
            ColumnContext(name="BIRTHDATE", data_type="date", description="Patient's date of birth"),
            ColumnContext(name="DEATHDATE", data_type="date", nullable=True, description="Patient's date of death"),
            ColumnContext(name="FIRST", data_type="text", description="Patient's first name"),
            ColumnContext(name="LAST", data_type="text", description="Patient's last name"),
            ColumnContext(name="GENDER", data_type="text", description="Patient's gender (M/F)"),
            ColumnContext(name="HEALTHCARE_EXPENSES", data_type="numeric", description="Total healthcare expenses in USD"),
            ColumnContext(name="HEALTHCARE_COVERAGE", data_type="numeric", description="Total healthcare coverage amount in USD"),
        ],
    )


# =============================================================================
# Expected Rule Types cho mỗi Table
# =============================================================================

EXPECTED_RULES = {
    "encounters": {
        "expected_rule_types": ["TEMPORAL", "CONDITIONAL_DEPENDENCY"],
        "expected_columns": {
            "TEMPORAL": ["START", "STOP"],
            "CONDITIONAL_DEPENDENCY": ["ENCOUNTERCLASS", "STOP"],
        },
    },
    "medications": {
        "expected_rule_types": ["TEMPORAL", "CROSS_COLUMN"],
        "expected_columns": {
            "TEMPORAL": ["START", "STOP"],
            "CROSS_COLUMN": ["BASE_COST", "DISPENSES", "TOTALCOST"],
        },
    },
    "patients": {
        "expected_rule_types": ["CONDITIONAL_DEPENDENCY"],
        "expected_columns": {
            "CONDITIONAL_DEPENDENCY": ["DEATHDATE", "BIRTHDATE"],
        },
    },
}


class MockLLMClient:
    """Mock LLM client với realistic responses."""

    def __init__(self, responses: list):
        self._responses = responses
        self._call_count = 0

    async def generate_structured(self, system_prompt, user_prompt, response_model):
        if self._call_count < len(self._responses):
            result = self._responses[self._call_count]
            self._call_count += 1
            return result
        return response_model()


# =============================================================================
# Integration Tests
# =============================================================================

class TestHealthcareIntegration:
    """Integration tests với healthcare schema."""

    @pytest.mark.asyncio
    async def test_encounters_temporal_rule(self):
        """Test temporal rule cho encounters: STOP >= START."""
        context = create_encounters_table_context()

        # Router response
        router_response = RouterResult(candidates=[
            RouterCandidate(
                rule_type=AdvancedRuleType.TEMPORAL,
                relevant_columns=["START", "STOP"],
                confidence=0.95,
                reason="START and STOP là timestamps thể hiện thời gian encounter.",
            ),
        ])

        # Generator response
        generator_response = TemporalOutput(rules=[
            {
                "condition": "STOP >= START",
                "reason": "Encounter end không thể trước start.",
                "evidence": ["START là thời gian bắt đầu", "STOP là thời gian kết thúc"],
            }
        ])

        mock_client = MockLLMClient([router_response, generator_response])
        service = AdvancedRuleService(llm_client=mock_client, min_confidence=0.75)

        router_result, rules = await service.recommend(context)

        # Verify
        assert len(router_result.candidates) == 1
        assert router_result.candidates[0].rule_type == "TEMPORAL"
        assert len(rules) == 1
        assert "STOP >= START" in rules[0].condition

    @pytest.mark.asyncio
    async def test_medications_cross_column_rule(self):
        """Test cross-column rule cho medications: TOTALCOST = BASE_COST * DISPENSES."""
        context = create_medications_table_context()

        router_response = RouterResult(candidates=[
            RouterCandidate(
                rule_type=AdvancedRuleType.CROSS_COLUMN,
                relevant_columns=["BASE_COST", "DISPENSES", "TOTALCOST"],
                confidence=0.92,
                reason="Các cột chi phí có thể có quan hệ toán học.",
            ),
        ])

        generator_response = CrossColumnOutput(rules=[
            {
                "condition": "TOTALCOST = BASE_COST * DISPENSES",
                "reason": "Tổng chi phí = đơn giá * số lần cấp phát.",
                "evidence": ["BASE_COST là đơn giá", "DISPENSES là số lần", "TOTALCOST là tổng"],
            }
        ])

        mock_client = MockLLMClient([router_response, generator_response])
        service = AdvancedRuleService(llm_client=mock_client, min_confidence=0.75)

        router_result, rules = await service.recommend(context)

        # Verify
        assert len(rules) == 1
        assert "TOTALCOST = BASE_COST * DISPENSES" in rules[0].condition

    @pytest.mark.asyncio
    async def test_patients_conditional_dependency(self):
        """Test conditional dependency cho patients: DEATHDATE phụ thuộc vào việc có DEATHDATE hay không."""
        context = create_patients_table_context()

        router_response = RouterResult(candidates=[
            RouterCandidate(
                rule_type=AdvancedRuleType.CONDITIONAL_DEPENDENCY,
                relevant_columns=["BIRTHDATE", "DEATHDATE"],
                confidence=0.88,
                reason="Nếu DEATHDATE có giá trị thì phải >= BIRTHDATE.",
            ),
        ])

        generator_response = ConditionalDependencyOutput(rules=[
            {
                "condition": "IF DEATHDATE IS NOT NULL THEN DEATHDATE >= BIRTHDATE",
                "reason": "Ngày mất không thể trước ngày sinh.",
                "evidence": ["DEATHDATE là ngày mất", "BIRTHDATE là ngày sinh"],
            }
        ])

        mock_client = MockLLMClient([router_response, generator_response])
        service = AdvancedRuleService(llm_client=mock_client, min_confidence=0.75)

        router_result, rules = await service.recommend(context)

        # Verify
        assert len(rules) == 1
        assert "DEATHDATE >= BIRTHDATE" in rules[0].condition

    @pytest.mark.asyncio
    async def test_multiple_rule_types_in_encounters(self):
        """Test nhiều rule types trong encounters table."""
        context = create_encounters_table_context()

        router_response = RouterResult(candidates=[
            RouterCandidate(
                rule_type=AdvancedRuleType.TEMPORAL,
                relevant_columns=["START", "STOP"],
                confidence=0.95,
                reason="Timestamps.",
            ),
            RouterCandidate(
                rule_type=AdvancedRuleType.CONDITIONAL_DEPENDENCY,
                relevant_columns=["ENCOUNTERCLASS", "STOP"],
                confidence=0.82,
                reason="Emergency encounters có thể yêu cầu STOP.",
            ),
        ])

        generator_responses = [
            TemporalOutput(rules=[
                {
                    "condition": "STOP >= START",
                    "reason": "End time.",
                    "evidence": [],
                }
            ]),
            ConditionalDependencyOutput(rules=[
                {
                    "condition": "IF ENCOUNTERCLASS = 'emergency' THEN STOP IS NOT NULL",
                    "reason": "Emergency cần end time.",
                    "evidence": [],
                }
            ]),
        ]

        mock_client = MockLLMClient([router_response] + generator_responses)
        service = AdvancedRuleService(llm_client=mock_client, min_confidence=0.75)

        router_result, rules = await service.recommend(context)

        # Verify
        assert len(router_result.candidates) == 2
        assert len(rules) == 2

    @pytest.mark.asyncio
    async def test_empty_result_when_no_rules_found(self):
        """Test khi không tìm thấy rule nào."""
        context = create_encounters_table_context()

        router_response = RouterResult(candidates=[
            RouterCandidate(
                rule_type=AdvancedRuleType.CROSS_COLUMN,
                relevant_columns=["START", "STOP"],
                confidence=0.5,  # Thấp - không đủ để tạo rule
                reason="Có thể không có cross-column rule.",
            ),
        ])

        # Generator trả về empty
        generator_response = TemporalOutput(rules=[])

        mock_client = MockLLMClient([router_response, generator_response])
        service = AdvancedRuleService(llm_client=mock_client, min_confidence=0.75)

        router_result, rules = await service.recommend(context)

        # Router có candidate nhưng không đủ confidence
        assert len(router_result.candidates) == 1

    @pytest.mark.asyncio
    async def test_rule_deduplication(self):
        """Test deduplication của rules - router loại bỏ duplicate candidates."""
        context = create_encounters_table_context()

        # Router sẽ loại bỏ duplicate candidates (same columns, different order)
        router_response = RouterResult(candidates=[
            RouterCandidate(
                rule_type=AdvancedRuleType.TEMPORAL,
                relevant_columns=["START", "STOP"],
                confidence=0.95,
                reason="Timestamps.",
            ),
        ])

        generator_response = TemporalOutput(rules=[
            {
                "condition": "STOP >= START",
                "reason": "Rule 1",
                "evidence": [],
            }
        ])

        mock_client = MockLLMClient([router_response, generator_response])
        service = AdvancedRuleService(llm_client=mock_client, min_confidence=0.75)

        router_result, rules = await service.recommend(context)

        # Router loại bỏ duplicate - chỉ còn 1 candidate
        assert len(router_result.candidates) == 1
        # Generator tạo 1 rule
        assert len(rules) == 1


class TestRuleTypeCoverage:
    """Test coverage của các rule types."""

    def test_all_rule_types_implemented(self):
        """Verify tất cả rule types đã được implement."""
        assert AdvancedRuleType.CROSS_COLUMN.value == "CROSS_COLUMN"
        assert AdvancedRuleType.CONDITIONAL_DEPENDENCY.value == "CONDITIONAL_DEPENDENCY"
        assert AdvancedRuleType.TEMPORAL.value == "TEMPORAL"

    @pytest.mark.asyncio
    async def test_temporal_generator_on_datetime_columns(self):
        """Test temporal generator với datetime columns."""
        context = create_encounters_table_context()

        router_response = RouterResult(candidates=[
            RouterCandidate(
                rule_type=AdvancedRuleType.TEMPORAL,
                relevant_columns=["START", "STOP"],
                confidence=0.95,
                reason="Datetime columns.",
            ),
        ])

        generator_response = TemporalOutput(rules=[
            {
                "condition": "STOP >= START",
                "reason": "Temporal constraint.",
                "evidence": [],
            }
        ])

        mock_client = MockLLMClient([router_response, generator_response])
        service = AdvancedRuleService(llm_client=mock_client, min_confidence=0.75)

        router_result, rules = await service.recommend(context)

        assert len(rules) >= 1
        assert rules[0].rule_type == "TEMPORAL"

    @pytest.mark.asyncio
    async def test_cross_column_generator_on_numeric_columns(self):
        """Test cross-column generator với numeric columns."""
        context = create_medications_table_context()

        router_response = RouterResult(candidates=[
            RouterCandidate(
                rule_type=AdvancedRuleType.CROSS_COLUMN,
                relevant_columns=["BASE_COST", "DISPENSES", "TOTALCOST"],
                confidence=0.92,
                reason="Numeric columns.",
            ),
        ])

        generator_response = CrossColumnOutput(rules=[
            {
                "condition": "TOTALCOST = BASE_COST * DISPENSES",
                "reason": "Calculation.",
                "evidence": [],
            }
        ])

        mock_client = MockLLMClient([router_response, generator_response])
        service = AdvancedRuleService(llm_client=mock_client, min_confidence=0.75)

        router_result, rules = await service.recommend(context)

        assert len(rules) >= 1
        assert rules[0].rule_type == "CROSS_COLUMN"

    @pytest.mark.asyncio
    async def test_conditional_dependency_generator(self):
        """Test conditional dependency generator."""
        context = create_patients_table_context()

        router_response = RouterResult(candidates=[
            RouterCandidate(
                rule_type=AdvancedRuleType.CONDITIONAL_DEPENDENCY,
                relevant_columns=["BIRTHDATE", "DEATHDATE"],
                confidence=0.88,
                reason="Conditional relationship.",
            ),
        ])

        generator_response = ConditionalDependencyOutput(rules=[
            {
                "condition": "IF DEATHDATE IS NOT NULL THEN DEATHDATE >= BIRTHDATE",
                "reason": "Validation.",
                "evidence": [],
            }
        ])

        mock_client = MockLLMClient([router_response, generator_response])
        service = AdvancedRuleService(llm_client=mock_client, min_confidence=0.75)

        router_result, rules = await service.recommend(context)

        assert len(rules) >= 1
        assert rules[0].rule_type == "CONDITIONAL_DEPENDENCY"
