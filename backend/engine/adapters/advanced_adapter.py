"""Adapter for advanced LLM rules and their rendered SQL."""

import asyncio

from backend.contracts.candidate_rule import CandidateRule
from backend.contracts.generation import (
    EngineGenerationResult,
    GenerationError,
    GenerationOptions,
    RuleEngine,
)
from backend.contracts.table_context import TableContext
from backend.engine.adapters.base import GenerationEngineAdapter
from backend.engine.advanced_rule_service import AdvancedRuleService
from backend.integrations.openmetadata.client import openmetadata_client
from backend.validator.existing_rule_reconciler import reconcile_generated_rules


def _description(rule_type: str, columns: list[str], reason: str) -> str:
    joined = ", ".join(columns[:3]) or "các cột"
    if len(columns) > 3:
        joined += "..."
    labels = {
        "TEMPORAL": "Ràng buộc thời gian",
        "CROSS_COLUMN": "Ràng buộc chéo cột",
        "CONDITIONAL_DEPENDENCY": "Ràng buộc điều kiện",
    }
    return f"{labels.get(rule_type, rule_type)}: {joined}" if not reason else reason[:160]


class AdvancedGenerationAdapter(GenerationEngineAdapter):
    engine = RuleEngine.ADVANCED

    async def generate(
        self,
        context: TableContext,
        table_fqn: str,
        options: GenerationOptions,
    ) -> EngineGenerationResult:
        service = AdvancedRuleService(min_confidence=options.min_confidence)
        raw = await service.recommend_with_sql(
            context,
            allowed_types=options.advanced_types,
        )
        generated = [
            CandidateRule(
                rule_type=rule.rule_type,
                description=_description(rule.rule_type, rule.columns, rule.reason),
                target_columns=rule.columns,
                parameters=rule.params,
                engine="ADVANCED",
                confidence=rule.confidence,
                reason=rule.reason,
                validation_status="INVALID" if rule.sql_error else "VALID",
                validation_message=rule.sql_error,
                status="DRAFT",
                sql=rule.sql,
                rendered_sql=rule.rendered_sql,
                violation_predicate=rule.violation_predicate,
                params=rule.params,
                conditions=rule.conditions,
            )
            for rule in raw.rules
        ]

        existing = await asyncio.to_thread(
            openmetadata_client.get_table_test_cases, table_fqn
        )
        displayed = generated
        reviewable = generated
        duplicates = 0
        warnings = []
        if existing.get("success"):
            displayed, reviewable, duplicates = reconcile_generated_rules(
                generated, existing.get("data", []), self.engine.value
            )
        else:
            warnings.append(
                f"Could not reconcile OpenMetadata Test Cases: {existing.get('error', 'unknown error')}"
            )

        errors = [
            GenerationError(
                step=str(item.get("step", "advanced")),
                message=str(item.get("error", "Unknown advanced generation error")),
            )
            for item in raw.errors
        ]
        status = "PARTIAL" if errors or raw.total_sql_failed else "SUCCESS"
        if not generated and errors:
            status = "FAILED"

        return EngineGenerationResult(
            engine=self.engine,
            table_fqn=table_fqn,
            table_name=context.table_name,
            status=status,
            rules=displayed,
            reviewable_rules=reviewable,
            generated_count=len(reviewable),
            existing_count=sum(rule.status == "APPLIED" for rule in displayed),
            duplicates_filtered=duplicates,
            llm_calls=1 + len(raw.candidates),
            warnings=warnings,
            errors=errors,
            metadata={
                "candidates": raw.candidates,
                "total_candidates": raw.total_candidates,
                "total_rules_generated": raw.total_rules_generated,
                "total_sql_mapped": raw.total_sql_mapped,
                "total_sql_failed": raw.total_sql_failed,
            },
        )
