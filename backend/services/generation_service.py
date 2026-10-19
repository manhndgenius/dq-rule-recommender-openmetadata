"""Single-table orchestration shared by current and future bulk APIs."""

from __future__ import annotations

from typing import Mapping

from backend.contracts.generation import (
    EngineGenerationResult,
    GenerationOptions,
    RuleEngine,
)
from backend.contracts.table_context import TableContext
from backend.engine.adapters.base import GenerationEngineAdapter
from backend.review.review_service import review_service
from backend.storage.generation_cache import generation_cache
from backend.storage.rule_identity import stable_rule_id
from backend.storage.rule_repository import rule_repository


class RulePersistenceError(RuntimeError):
    """Raised when generated rules cannot be durably stored."""


class GenerationService:
    def __init__(self, adapters: Mapping[RuleEngine, GenerationEngineAdapter]):
        self.adapters = dict(adapters)

    async def generate(
        self,
        context: TableContext,
        table_fqn: str,
        engine: RuleEngine,
        options: GenerationOptions | None = None,
        persist: bool = True,
    ) -> EngineGenerationResult:
        adapter = self.adapters[engine]
        result = await adapter.generate(
            context=context,
            table_fqn=table_fqn,
            options=options or GenerationOptions(),
        )

        # IDs must be stable before entering in-memory review or PostgreSQL.
        for rule in result.rules:
            rule.id = stable_rule_id(
                table_fqn,
                engine.value,
                rule.model_dump(),
            )
        reviewable_ids = {rule.id for rule in result.reviewable_rules}
        result.reviewable_rules = [
            rule for rule in result.rules if rule.id in reviewable_ids and rule.status != "APPLIED"
        ]
        # Some reconciliations copy candidates, so match again by generated
        # identity when the copied ID set no longer points at displayed rules.
        if result.generated_count and not result.reviewable_rules:
            result.reviewable_rules = [rule for rule in result.rules if rule.status != "APPLIED"]

        review_service.save_candidates(result.reviewable_rules)
        generation_cache.save(table_fqn, engine.value, result.rules)
        if persist and result.rules:
            try:
                rule_repository.save_rules(
                    table_fqn=table_fqn,
                    engine=engine.value,
                    rules=[rule.model_dump() for rule in result.rules],
                    generation_metadata={
                        "warnings": result.warnings,
                        "errors": [error.model_dump() for error in result.errors],
                        "llm_calls": result.llm_calls,
                        **result.metadata,
                    },
                )
            except Exception as exc:
                raise RulePersistenceError(
                    f"Cannot persist {engine.value} rules for {table_fqn}"
                ) from exc
        return result
