"""
Module E — Statistical Rules Service / Orchestration.

Điều phối: prefilter → build context → LLM review → validate → response.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from backend.contracts.table_context import TableContext
from backend.engine.statistical_rules.contracts import (
    DiagnosticEntry,
    LLMSuggestion,
    LLMSuggestionResult,
    PreFilterResult,
    StatisticalRecommendationResponse,
    StatisticalRuleCandidate,
    SummaryStats,
)
from backend.engine.statistical_rules.llm_reviewer import (
    build_llm_context,
    validate_and_convert_decisions,
)
from backend.engine.statistical_rules.prefilter import prefilter_column, prefilter_table

logger = logging.getLogger(__name__)

# Load system prompt from file
_PROMPT_PATH = Path(__file__).parent / "prompts" / "system_prompt.md"
SYSTEM_PROMPT = _PROMPT_PATH.read_text(encoding="utf-8")


class StatisticalRulesService:
    """Service chính cho statistical rules recommendation."""

    def __init__(self):
        self._llm_client = None

    @property
    def llm_client(self):
        """Lazy load LLM client."""
        if self._llm_client is None:
            from backend.engine.advanced_llm.client import LLMClient
            self._llm_client = LLMClient()
        return self._llm_client

    def prefilter_only(
        self,
        table: TableContext,
    ) -> StatisticalRecommendationResponse:
        """
        Chỉ chạy prefilter, không gọi LLM.
        Dùng để test hoặc khi LLM không khả dụng.
        """
        # Pre-filter
        prefilter_results = prefilter_table(table)

        # Build filtered diagnostics
        filtered = self._build_filtered_diagnostics(prefilter_results)

        # Count stats
        eligible_pairs = self._collect_eligible_pairs(prefilter_results)
        summary = SummaryStats(
            columns_scanned=len(table.columns),
            eligible_columns=sum(1 for r in prefilter_results if r.eligible_rules),
            eligible_pairs=len(eligible_pairs),
            filtered_pairs=sum(len(r.filtered_rules) for r in prefilter_results),
            llm_calls=0,
        )

        return StatisticalRecommendationResponse(
            table_fqn=f"{table.database_name}.{table.schema_name}.{table.table_name}",
            table_name=table.table_name,
            profile_timestamp=table.columns[0].profile.profile_timestamp if table.columns else None,
            summary=summary,
            recommendations=[],
            skipped=[],
            uncertain=[],
            filtered=filtered,
            warnings=[],
        )

    async def recommend(
        self,
        table: TableContext,
        use_llm: bool = True,
    ) -> StatisticalRecommendationResponse:
        """
        Main recommendation pipeline.

        Args:
            table: Table context từ OpenMetadata
            use_llm: Có gọi LLM review không

        Returns:
            Recommendation response với candidates
        """
        # Step 1: Pre-filter
        prefilter_results = prefilter_table(table)

        # Build filtered diagnostics
        filtered = self._build_filtered_diagnostics(prefilter_results)

        # Collect all eligible pairs
        eligible_pairs = self._collect_eligible_pairs(prefilter_results)

        # Count stats
        summary = SummaryStats(
            columns_scanned=len(table.columns),
            eligible_columns=sum(1 for r in prefilter_results if r.eligible_rules),
            eligible_pairs=len(eligible_pairs),
            filtered_pairs=sum(len(r.filtered_rules) for r in prefilter_results),
            llm_calls=0,
        )

        # No eligible pairs
        if not eligible_pairs:
            return StatisticalRecommendationResponse(
                table_fqn=f"{table.database_name}.{table.schema_name}.{table.table_name}",
                table_name=table.table_name,
                summary=summary,
                recommendations=[],
                skipped=[],
                uncertain=[],
                filtered=filtered,
                warnings=["No eligible columns for statistical rules after prefilter."],
            )

        # No LLM requested
        if not use_llm:
            return StatisticalRecommendationResponse(
                table_fqn=f"{table.database_name}.{table.schema_name}.{table.table_name}",
                table_name=table.table_name,
                summary=summary,
                recommendations=[],
                skipped=[],
                uncertain=[],
                filtered=filtered,
                warnings=["use_llm=False - returning only prefilter results."],
            )

        # Step 2: Build LLM context
        llm_context = build_llm_context(table, prefilter_results)
        if not llm_context:
            return StatisticalRecommendationResponse(
                table_fqn=f"{table.database_name}.{table.schema_name}.{table.table_name}",
                table_name=table.table_name,
                summary=summary,
                recommendations=[],
                skipped=[],
                uncertain=[],
                filtered=filtered,
                warnings=["No eligible pairs for LLM review."],
            )

        # Step 3: LLM review
        try:
            llm_result = await self.llm_client.generate_structured(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=llm_context.model_dump_json(),
                response_model=LLMSuggestionResult,
            )
            llm_decisions = llm_result.decisions
        except Exception as e:
            logger.error(f"LLM review failed: {e}")
            # All pairs become UNCERTAIN
            llm_decisions = []

        # Step 4: Validate and convert
        candidates = validate_and_convert_decisions(
            llm_decisions=llm_decisions,
            expected_pairs=eligible_pairs,
        )

        # Update summary
        summary.llm_calls = 1
        summary.recommended_pairs = sum(1 for c in candidates if c.decision == LLMSuggestion.RECOMMEND)
        summary.skipped_pairs = sum(1 for c in candidates if c.decision == LLMSuggestion.SKIP)
        summary.uncertain_pairs = sum(1 for c in candidates if c.decision == LLMSuggestion.UNCERTAIN)

        # Separate by decision
        recommendations = [c for c in candidates if c.decision == LLMSuggestion.RECOMMEND]
        skipped = [c for c in candidates if c.decision == LLMSuggestion.SKIP]
        uncertain = [c for c in candidates if c.decision == LLMSuggestion.UNCERTAIN]

        return StatisticalRecommendationResponse(
            table_fqn=f"{table.database_name}.{table.schema_name}.{table.table_name}",
            table_name=table.table_name,
            profile_timestamp=table.columns[0].profile.profile_timestamp if table.columns else None,
            summary=summary,
            recommendations=recommendations,
            skipped=skipped,
            uncertain=uncertain,
            filtered=filtered,
            warnings=[],
        )

    def _build_filtered_diagnostics(
        self,
        prefilter_results: List[PreFilterResult],
    ) -> List[DiagnosticEntry]:
        """Build diagnostic entries từ prefilter results."""
        diagnostics = []
        for result in prefilter_results:
            if not result.eligible_rules and result.filtered_rules:
                # Column was filtered
                first_filter = result.filtered_rules[0]
                diagnostics.append(DiagnosticEntry(
                    column=result.column_name,
                    status="FILTERED",
                    reason_codes=[fr.reason_code for fr in result.filtered_rules],
                    message=f"Column filtered: {first_filter.reason_code}",
                ))
            elif result.eligible_rules:
                # Column has some filtered rules
                filtered = [fr for fr in result.filtered_rules]
                if filtered:
                    diagnostics.append(DiagnosticEntry(
                        column=result.column_name,
                        status="PARTIALLY_FILTERED",
                        reason_codes=[fr.reason_code for fr in filtered],
                        message=f"Partial filter: {len(filtered)} rules filtered",
                    ))
        return diagnostics

    def _collect_eligible_pairs(
        self,
        prefilter_results: List[PreFilterResult],
    ) -> List[tuple]:
        """Collect all eligible (column, rule_type) pairs."""
        pairs = []
        for result in prefilter_results:
            for rule in result.eligible_rules:
                pairs.append((result.column_name, rule))
        return pairs


# Singleton instance
statistical_rules_service = StatisticalRulesService()
