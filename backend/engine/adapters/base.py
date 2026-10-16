"""Base helpers shared by generation engine adapters."""

from __future__ import annotations

from abc import ABC, abstractmethod

from backend.contracts.generation import (
    EngineGenerationResult,
    GenerationOptions,
    RuleEngine,
)
from backend.contracts.table_context import TableContext


def context_fqn(context: TableContext, requested_fqn: str | None = None) -> str:
    return (
        requested_fqn
        or context.table_fqn
        or f"{context.database_name}.{context.schema_name}.{context.table_name}"
    )


class GenerationEngineAdapter(ABC):
    engine: RuleEngine

    @abstractmethod
    async def generate(
        self,
        context: TableContext,
        table_fqn: str,
        options: GenerationOptions,
    ) -> EngineGenerationResult:
        """Generate normalized candidates for exactly one table."""
