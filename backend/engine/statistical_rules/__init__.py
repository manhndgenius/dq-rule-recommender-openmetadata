"""
Statistical Rules Engine — Simplified v2.

Module B: prefilter (hard filter)
Module C: build_llm_context
Module D: llm_reviewer
Module E: service (orchestration)

API: POST /recommendations/statistical/generate
"""

from backend.engine.statistical_rules.contracts import (
    DiagnosticEntry,
    FilteredRule,
    LLMSuggestion,
    LLMSuggestionContext,
    LLMSuggestionDecision,
    LLMSuggestionResult,
    LLMColumnReview,
    PreFilterResult,
    StatisticalRecommendationResponse,
    StatisticalProfilePoint,
    StatisticalRuleCandidate,
    SummaryStats,
    ThresholdStatus,
)
from backend.engine.statistical_rules.prefilter import prefilter_column, prefilter_table
from backend.engine.statistical_rules.service import (
    StatisticalRulesService,
    statistical_rules_service,
)

__all__ = [
    "PreFilterResult",
    "FilteredRule",
    "LLMSuggestionContext",
    "LLMColumnReview",
    "LLMSuggestionDecision",
    "LLMSuggestionResult",
    "LLMSuggestion",
    "StatisticalRuleCandidate",
    "DiagnosticEntry",
    "StatisticalRecommendationResponse",
    "StatisticalProfilePoint",
    "SummaryStats",
    "ThresholdStatus",
    "prefilter_column",
    "prefilter_table",
    "StatisticalRulesService",
    "statistical_rules_service",
]
