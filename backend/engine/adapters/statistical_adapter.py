"""Adapter for LLM-reviewed statistical recommendations."""

import asyncio

from backend.contracts.candidate_rule import CandidateRule
from backend.contracts.generation import (
    EngineGenerationResult,
    GenerationOptions,
    RuleEngine,
)
from backend.contracts.table_context import TableContext
from backend.engine.adapters.base import GenerationEngineAdapter
from backend.engine.statistical_rules import statistical_rules_service
from backend.engine.statistical_rules.profile_history import (
    enrich_recommendation_profile_history,
)
from backend.integrations.openmetadata.client import openmetadata_client
from backend.validator.existing_rule_reconciler import reconcile_generated_rules


class StatisticalGenerationAdapter(GenerationEngineAdapter):
    engine = RuleEngine.STATISTICAL

    async def generate(
        self,
        context: TableContext,
        table_fqn: str,
        options: GenerationOptions,
    ) -> EngineGenerationResult:
        response = await statistical_rules_service.recommend(
            table=context,
            use_llm=options.use_llm,
        )
        response.table_fqn = table_fqn
        await asyncio.to_thread(
            enrich_recommendation_profile_history,
            response,
            table_fqn,
            openmetadata_client,
            options.profile_history_limit,
        )

        generated = [
            CandidateRule(
                id=candidate.id,
                rule_type=candidate.rule_type,
                target_columns=[candidate.column],
                parameters=candidate.parameters,
                engine="STATISTICAL",
                confidence=1.0,
                reason=candidate.reason,
                evidence=candidate.evidence,
                profile_metric=candidate.profile_metric,
                profile_history=[point.model_dump() for point in candidate.profile_history],
                threshold_status=candidate.threshold_status.value,
                status="DRAFT",
            )
            for candidate in response.recommendations
        ]

        existing = await asyncio.to_thread(
            openmetadata_client.get_table_test_cases, table_fqn
        )
        displayed = generated
        reviewable = generated
        duplicates = 0
        warnings = list(response.warnings)
        if existing.get("success"):
            displayed, reviewable, duplicates = reconcile_generated_rules(
                generated, existing.get("data", []), self.engine.value
            )
        else:
            warnings.append(
                f"Could not reconcile OpenMetadata Test Cases: {existing.get('error', 'unknown error')}"
            )

        return EngineGenerationResult(
            engine=self.engine,
            table_fqn=table_fqn,
            table_name=context.table_name,
            rules=displayed,
            reviewable_rules=reviewable,
            generated_count=len(reviewable),
            existing_count=sum(rule.status == "APPLIED" for rule in displayed),
            duplicates_filtered=duplicates,
            llm_calls=response.summary.llm_calls,
            warnings=warnings,
            metadata={
                "summary": response.summary.model_dump(),
                "filtered": [item.model_dump() for item in response.filtered],
                "skipped": [item.model_dump() for item in response.skipped],
                "uncertain": [item.model_dump() for item in response.uncertain],
                "profile_timestamp": response.profile_timestamp,
            },
        )
