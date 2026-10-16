"""
Module D — LLM Semantic Rule Reviewer.

Gọi LLM để review eligible pairs và quyết định RECOMMEND/SKIP/UNCERTAIN.
Reuse LLM client từ advanced_llm/client.py.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.contracts.table_context import TableContext
from backend.engine.statistical_rules.contracts import (
    LLMSuggestion,
    LLMSuggestionContext,
    LLMSuggestionDecision,
    LLMSuggestionResult,
    LLMColumnReview,
    PreFilterResult,
    StatisticalRuleCandidate,
)

logger = logging.getLogger(__name__)

# Load system prompt from file
_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.md"
SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")

# Mapping từ short alias sang OpenMetadata rule type
RULE_ALIAS_TO_TYPE = {
    "mean": "columnValueMeanToBeBetween",
    "median": "columnValueMedianToBeBetween",
    "stddev": "columnValueStdDevToBeBetween",
}

# Reverse mapping
RULE_TYPE_TO_ALIAS = {v: k for k, v in RULE_ALIAS_TO_TYPE.items()}


def build_llm_context(
    table: TableContext,
    prefilter_results: List[PreFilterResult],
) -> Optional[LLMSuggestionContext]:
    """
    Build LLM context theo format grouped by column.

    Format mới:
    - table: table info
    - columns: all columns (schema + eligible profile/rules)
    - existing_rules: list of existing rule types

    Returns:
        LLMSuggestionContext or None if no eligible pairs
    """
    # Build lookup cho prefilter results
    prefilter_map = {r.column_name: r for r in prefilter_results}

    # Build columns list
    columns: List[LLMColumnReview] = []

    for col in table.columns:
        prefilter = prefilter_map.get(col.name)

        # Schema cơ bản cho tất cả columns
        schema_entry = LLMColumnReview(
            name=col.name,
            datatype=col.data_type or "",
            description=col.description or "",
            is_pk=col.is_primary_key,
            is_fk=col.is_foreign_key,
        )

        # Nếu có eligible rules, thêm profile và rules
        if prefilter and prefilter.eligible_rules:
            profile_dict = _build_profile_dict(col)
            # Convert rule types sang aliases
            rule_aliases = [RULE_TYPE_TO_ALIAS.get(rt, rt) for rt in prefilter.eligible_rules]

            schema_entry.profile = profile_dict
            schema_entry.rules = rule_aliases

        columns.append(schema_entry)

    # Table info
    table_info = {
        "fqn": f"{table.database_name}.{table.schema_name}.{table.table_name}",
        "name": table.table_name,
        "description": table.table_description or "",
    }

    # Existing rules
    existing_rules = [r.get("rule_type", "") for r in table.existing_rules if isinstance(r, dict)]

    return LLMSuggestionContext(
        table=table_info,
        columns=columns,
        existing_rules=existing_rules,
    )


def _build_profile_dict(col) -> Dict[str, Any]:
    """Build profile dict cho một column."""
    profile = col.profile
    p_dict = {
        "values_count": profile.values_count,
        "distinct_count": profile.distinct_count,
        "mean": profile.mean,
        "median": profile.median,
        "stddev": profile.stddev,
        "min": profile.min_value,
        "max": profile.max_value,
        "q1": profile.q1,
        "q3": profile.q3,
        "iqr": profile.iqr,
        "skew": profile.non_parametric_skew,
    }
    # Remove None values
    return {k: v for k, v in p_dict.items() if v is not None}


def get_eligible_pairs(
    prefilter_results: List[PreFilterResult],
) -> List[Tuple[str, str]]:
    """
    Extract eligible (column, rule_type) pairs từ prefilter results.
    Dùng để validate LLM output.
    """
    pairs = []
    for result in prefilter_results:
        for rule in result.eligible_rules:
            pairs.append((result.column_name, rule))
    return pairs


async def review_with_llm(
    context: LLMSuggestionContext,
    llm_client: Any,
) -> List[LLMSuggestionDecision]:
    """
    Gọi LLM để review candidates.

    Args:
        context: LLM context
        llm_client: LLM client instance

    Returns:
        List of decisions
    """
    try:
        user_prompt = context.model_dump_json()

        result = await llm_client.generate_structured(
            system_prompt=SYSTEM_PROMPT,
            user_prompt=user_prompt,
            response_model=LLMSuggestionResult,
        )

        return result.decisions

    except Exception as e:
        logger.error(f"LLM review failed: {e}")
        return []


def validate_and_convert_decisions(
    llm_decisions: List[LLMSuggestionDecision],
    expected_pairs: List[Tuple[str, str]],  # [(column, rule_type)]
    default_reason: str = "LLM_OUTPUT_INVALID_OR_MISSING",
) -> List[StatisticalRuleCandidate]:
    """
    Validate LLM decisions và convert sang StatisticalRuleCandidate.

    - Missing decisions → UNCERTAIN
    - Invalid decisions → filtered out
    - Chỉ cần candidate_id, backend tự parse column/rule
    """
    # Build expected IDs với cả full type và alias
    expected_ids: set = set()
    for col, rule in expected_pairs:
        expected_ids.add(f"{col}::{rule}")
        alias = RULE_TYPE_TO_ALIAS.get(rule, rule)
        expected_ids.add(f"{col}::{alias}")

    seen_ids = set()
    candidates = []

    for decision in llm_decisions:
        candidate_id = decision.candidate_id

        # Validate: must be in expected pairs
        if candidate_id not in expected_ids:
            logger.warning(f"LLM returned unknown candidate_id: {candidate_id}")
            continue

        # Validate: decision must be valid enum
        if decision.decision not in (LLMSuggestion.RECOMMEND, LLMSuggestion.SKIP, LLMSuggestion.UNCERTAIN):
            logger.warning(f"Invalid decision value: {decision.decision}")
            continue

        # Parse column và rule từ candidate_id
        # Format: "column_name::rule_alias" hoặc "column_name::rule_type"
        parts = candidate_id.rsplit("::", 1)
        if len(parts) != 2:
            logger.warning(f"Invalid candidate_id format: {candidate_id}")
            continue

        col_name, rule_ref = parts[0], parts[1]
        # Convert alias sang full rule type
        rule_type = RULE_ALIAS_TO_TYPE.get(rule_ref, rule_ref)

        seen_ids.add(candidate_id)
        candidates.append(StatisticalRuleCandidate(
            column=col_name,
            rule_type=rule_type,
            decision=decision.decision,
            reason=decision.reason,
            evidence={"llm_decision": decision.decision.value},
        ))

    # Fill missing decisions as UNCERTAIN
    for col, rule in expected_pairs:
        full_id = f"{col}::{rule}"
        alias_id = f"{col}::{RULE_TYPE_TO_ALIAS.get(rule, rule)}"

        if full_id not in seen_ids and alias_id not in seen_ids:
            candidates.append(StatisticalRuleCandidate(
                column=col,
                rule_type=rule,
                decision=LLMSuggestion.UNCERTAIN,
                reason=default_reason,
                evidence={"error": "missing_from_llm_output"},
            ))

    return candidates
