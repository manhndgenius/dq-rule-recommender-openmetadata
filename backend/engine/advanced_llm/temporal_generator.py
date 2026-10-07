"""Temporal Generator - tạo các time-ordering constraint rules."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from backend.contracts.table_context import TableContext
from backend.contracts.advanced_rule_router import RouterCandidate
from backend.contracts.advanced_rule import GeneratorResult, GeneratedRule
from backend.engine.advanced_llm.client import LLMClient
from backend.engine.advanced_llm.base_generator import BaseRuleGenerator
from backend.engine.advanced_llm.cross_column_generator import GeneratorError

logger = logging.getLogger(__name__)


class TemporalOutput(BaseModel):
    """Output model cho Temporal Generator - new format.

    Hỗ trợ cả old format (rules array) và new format (direct fields).
    """

    # New format: LLM trả về rule trực tiếp
    table: str | None = None
    columns: list[str] = Field(default_factory=list)
    rule_type: str = "TEMPORAL"
    conditions: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.8
    reason: str = ""

    # Legacy: old format
    rules: list[dict[str, Any]] = Field(default_factory=list)


class TemporalGenerator(BaseRuleGenerator):
    """Generator tạo TEMPORAL rules - các time-ordering constraints."""

    DEFAULT_PROMPT_FILE = "temporal.md"

    def __init__(self, llm_client: LLMClient, prompt_file: str | None = None):
        """Khởi tạo Temporal Generator.

        Args:
            llm_client: LLM client để gọi API.
            prompt_file: Tên file prompt (mặc định: temporal.md).
        """
        super().__init__(llm_client, prompt_file)
        self._prompt_path = (
            Path(__file__).parent.parent / "prompts" / self._prompt_file
        )

    def _load_prompt(self) -> str:
        """Load temporal prompt template."""
        return self._prompt_path.read_text(encoding="utf-8")

    async def generate(
        self,
        context: TableContext,
        candidate: RouterCandidate,
    ) -> GeneratorResult:
        """Tạo các TEMPORAL rules.

        Args:
            context: Full table context.
            candidate: Router candidate với columns đã chọn.

        Returns:
            GeneratorResult chứa các generated rules.
        """
        logger.info(
            f"Temporal Generator cho {context.table_name}, "
            f"columns: {candidate.relevant_columns}"
        )

        # Build context cho generator
        generator_context = self._build_generator_context(context, candidate)
        user_prompt = self._build_user_prompt(generator_context)

        # Gọi LLM
        try:
            result = await self._llm.generate_structured(
                system_prompt=self._load_prompt(),
                user_prompt=user_prompt,
                response_model=TemporalOutput,
            )
        except Exception as e:
            logger.error(f"Temporal Generator thất bại: {e}")
            raise GeneratorError(f"Temporal Generator thất bại: {e}") from e

        # Convert sang GeneratedRule models
        generated_rules = self._convert_to_rules(result, context.table_name, candidate)

        # Validate rules
        valid_column_names = {col.name for col in context.columns}
        validated_rules = self._validate_rules(generated_rules, valid_column_names)

        logger.info(
            f"Temporal Generator tạo được {len(validated_rules)} rules"
        )

        return GeneratorResult(rules=validated_rules)

    def _build_user_prompt(self, context: dict[str, Any]) -> str:
        """Build user prompt với serialized context."""
        return json.dumps(context, indent=2, default=str)

    def _convert_to_rules(
        self,
        llm_result: TemporalOutput,
        table_name: str,
        candidate: RouterCandidate,
    ) -> list[GeneratedRule]:
        """Convert LLM output sang GeneratedRule models.

        Hỗ trợ cả old format (rules array) và new format (direct fields với conditions).
        """
        rules = []

        # Check if LLM returned new format (has conditions)
        if llm_result.conditions:
            try:
                rule = GeneratedRule(
                    rule_type=candidate.rule_type,
                    target_table=table_name,
                    columns=candidate.relevant_columns,
                    conditions=llm_result.conditions,
                    reason=llm_result.reason or candidate.reason,
                    confidence=min(llm_result.confidence, candidate.confidence),
                )
                rules.append(rule)
                logger.info(f"Converted temporal rule với {len(llm_result.conditions)} conditions")
                return rules
            except Exception as e:
                logger.warning(f"Không thể convert rule mới: {e}")

        # Fallback: Check if LLM returned old format (rules array)
        if llm_result.rules:
            for rule_data in llm_result.rules:
                try:
                    rule = GeneratedRule(
                        rule_type=candidate.rule_type,
                        target_table=table_name,
                        columns=candidate.relevant_columns,
                        condition=rule_data.get("condition", ""),
                        reason=rule_data.get("reason", ""),
                        confidence=min(candidate.confidence, 0.92),
                        evidence=rule_data.get("evidence", []),
                    )
                    rules.append(rule)
                except Exception as e:
                    logger.warning(f"Bỏ qua rule không hợp lệ: {e}")

        return rules
