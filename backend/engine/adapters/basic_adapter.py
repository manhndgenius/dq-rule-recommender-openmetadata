"""Adapter for deterministic BASIC recommendations."""

import asyncio

from backend.contracts.generation import (
    EngineGenerationResult,
    GenerationOptions,
    RuleEngine,
)
from backend.contracts.table_context import TableContext
from backend.engine.adapters.base import GenerationEngineAdapter
from backend.engine.basic_engine import BasicRuleEngine
from backend.integrations.openmetadata.client import openmetadata_client
from backend.validator.existing_rule_reconciler import reconcile_generated_rules


class BasicGenerationAdapter(GenerationEngineAdapter):
    engine = RuleEngine.BASIC

    def __init__(self, rule_engine: BasicRuleEngine | None = None):
        self.rule_engine = rule_engine or BasicRuleEngine()

    async def generate(
        self,
        context: TableContext,
        table_fqn: str,
        options: GenerationOptions,
    ) -> EngineGenerationResult:
        generated = await asyncio.to_thread(self.rule_engine.generate_candidates, context)
        displayed = generated
        reviewable = generated
        duplicate_count = 0
        existing_count = 0

        existing = await asyncio.to_thread(
            openmetadata_client.get_table_test_cases, table_fqn
        )
        warnings = []
        if existing.get("success"):
            displayed, reviewable, duplicate_count = reconcile_generated_rules(
                generated, existing.get("data", []), self.engine.value
            )
            existing_count = sum(rule.status == "APPLIED" for rule in displayed)
        else:
            warnings.append(
                f"Could not reconcile OpenMetadata Test Cases: {existing.get('error', 'unknown error')}"
            )

        return EngineGenerationResult(
            engine=self.engine,
            table_fqn=table_fqn,
            table_name=getattr(context, "table_name", table_fqn.split(".")[-1]),
            rules=displayed,
            reviewable_rules=reviewable,
            generated_count=len(reviewable),
            existing_count=existing_count,
            duplicates_filtered=duplicate_count,
            warnings=warnings,
            metadata={"row_count": context.row_count},
        )
