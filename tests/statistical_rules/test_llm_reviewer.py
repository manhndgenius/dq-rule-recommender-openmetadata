"""Tests for the grouped statistical-rule LLM contract."""

from backend.contracts.table_context import ColumnContext, ColumnProfile, TableContext
from backend.engine.statistical_rules.contracts import (
    LLMSuggestion,
    LLMSuggestionDecision,
)
from backend.engine.statistical_rules.llm_reviewer import (
    RULE_ALIAS_TO_TYPE,
    SYSTEM_PROMPT,
    build_llm_context,
    get_eligible_pairs,
    validate_and_convert_decisions,
)
from backend.engine.statistical_rules.prefilter import prefilter_table


def _numeric_table() -> TableContext:
    return TableContext(
        database_name="test_db",
        schema_name="public",
        table_name="patients",
        table_description="Patient master data",
        columns=[
            ColumnContext(
                name="income",
                data_type="NUMERIC",
                description="Annual patient income",
                profile=ColumnProfile(
                    row_count=1000,
                    values_count=980,
                    mean=75000.0,
                    median=55000.0,
                    stddev=50000.0,
                    min_value=0.0,
                    max_value=500000.0,
                ),
            )
        ],
    )


def test_context_only_exposes_three_supported_rule_candidates():
    table = _numeric_table()
    prefilter_results = prefilter_table(table)

    context = build_llm_context(table, prefilter_results)

    assert context is not None
    assert context.columns[0].rules == ["mean", "median", "stddev"]
    assert set(RULE_ALIAS_TO_TYPE) == {"mean", "median", "stddev"}
    # Min/max remain useful profile context but are not candidates.
    assert context.columns[0].profile["min"] == 0.0
    assert context.columns[0].profile["max"] == 500000.0


def test_unknown_min_max_decisions_are_not_converted_to_candidates():
    table = _numeric_table()
    prefilter_results = prefilter_table(table)
    expected_pairs = get_eligible_pairs(prefilter_results)
    decisions = [
        LLMSuggestionDecision(
            candidate_id="income::min",
            decision=LLMSuggestion.RECOMMEND,
            reason="Unsupported rule",
        ),
        LLMSuggestionDecision(
            candidate_id="income::max",
            decision=LLMSuggestion.RECOMMEND,
            reason="Unsupported rule",
        ),
    ]

    candidates = validate_and_convert_decisions(decisions, expected_pairs)

    assert len(candidates) == 3
    assert {candidate.rule_type for candidate in candidates} == set(
        RULE_ALIAS_TO_TYPE.values()
    )
    assert all(candidate.decision == LLMSuggestion.UNCERTAIN for candidate in candidates)


def test_statistical_context_serializes_as_compact_json():
    table = _numeric_table()
    context = build_llm_context(table, prefilter_table(table))

    assert context is not None
    prompt = context.model_dump_json()
    assert "\n" not in prompt
    assert ": " not in prompt


def test_missing_llm_decision_becomes_uncertain():
    table = _numeric_table()
    prefilter_results = prefilter_table(table)
    expected_pairs = get_eligible_pairs(prefilter_results)
    decisions = [
        LLMSuggestionDecision(
            candidate_id="income::mean",
            decision=LLMSuggestion.RECOMMEND,
            reason="Average income has a concrete monitoring use.",
        )
    ]

    candidates = validate_and_convert_decisions(decisions, expected_pairs)
    by_rule = {candidate.rule_type: candidate for candidate in candidates}

    assert by_rule["columnValueMeanToBeBetween"].decision == LLMSuggestion.RECOMMEND
    assert by_rule["columnValueMedianToBeBetween"].decision == LLMSuggestion.UNCERTAIN
    assert by_rule["columnValueStdDevToBeBetween"].decision == LLMSuggestion.UNCERTAIN


def test_system_prompt_enforces_supported_rules_and_necessity_gate():
    assert "You may ONLY evaluate these three rules" in SYSTEM_PROMPT
    assert "The allowed rule aliases are: mean, median, stddev" in SYSTEM_PROMPT
    assert "The default decision is not RECOMMEND" in SYSTEM_PROMPT
    assert "Do not recommend both Mean and Median merely" in SYSTEM_PROMPT
    assert "Recommend StdDev only when variability itself" in SYSTEM_PROMPT
    assert "Write every `reason` value in clear, natural Vietnamese" in SYSTEM_PROMPT
    assert "Never return an English-only reason" in SYSTEM_PROMPT
    assert "including reasons for SKIP and UNCERTAIN" in SYSTEM_PROMPT
