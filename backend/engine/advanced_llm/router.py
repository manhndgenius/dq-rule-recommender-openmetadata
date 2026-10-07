"""Router phát hiện các loại advanced rule tiềm năng trong bảng."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from backend.contracts.table_context import TableContext

from backend.engine.advanced_llm.client import LLMClient
from backend.contracts import RouterResult, RouterCandidate, AdvancedRuleType

logger = logging.getLogger(__name__)


class AdvancedRuleRouter:
    """Router phát hiện các loại advanced rule tiềm năng trong bảng."""

    def __init__(self, llm_client: LLMClient, prompt_file: str = "advanced_router_3.md"):
        """Khởi tạo router.

        Args:
            llm_client: LLM client để gọi API.
            prompt_file: Tên file prompt trong prompts/ (không có đường dẫn).
                       Ví dụ: "advanced_router.md" hoặc "advanced_router_2.md"
        """
        self._llm = llm_client
        self._prompt_path = Path(__file__).parent.parent / "prompts" / prompt_file
        self._prompt_file = prompt_file

    def _load_prompt(self) -> str:
        """Load router prompt template."""
        return self._prompt_path.read_text(encoding="utf-8")

    async def route(self, context: TableContext) -> RouterResult:
        """Phát hiện các advanced rule tiềm năng trong bảng.

        Args:
            context: Table context chứa metadata và profiling.

        Returns:
            RouterResult chứa các candidates đã phát hiện.
        """
        logger.info(f"Routing table: {context.table_name}")

        # Build compact context cho router
        router_context = self._build_router_context(context)
        user_prompt = self._build_user_prompt(router_context)

        # Gọi LLM
        try:
            result = await self._llm.generate_structured(
                system_prompt=self._load_prompt(),
                user_prompt=user_prompt,
                response_model=RouterResult,
            )
        except Exception as e:
            logger.error(f"Router thất bại: {e}")
            raise RouterError(f"Router thất bại: {e}") from e

        # Post-validate candidates
        validated = self._post_validate(context, result)

        logger.info(
            f"Router tìm thấy {len(validated.candidates)} candidates cho {context.table_name}"
        )

        return validated

    def _build_router_context(self, context: TableContext) -> dict[str, Any]:
        """Build compact context cho router.

        Args:
            context: Full table context.

        Returns:
            Compact context dict cho router.
        """
        columns = []
        for col in context.columns:
            col_data = {
                "name": col.name,
                "datatype": col.data_type,
                "nullable": col.nullable,
                "is_primary_key": col.is_primary_key,
                "is_foreign_key": col.is_foreign_key,
            }
            if col.description:
                col_data["description"] = col.description
            if col.profile:
                col_data["profiling"] = self._extract_profiling(col.profile)
            columns.append(col_data)

        router_context = {
            "table": {
                "name": context.table_name,
                "schema": context.schema_name,
                "database": context.database_name,
            },
            "columns": columns,
        }

        if context.table_description:
            router_context["table"]["description"] = context.table_description

        # Bổ sung constraint metadata
        if context.primary_keys:
            router_context["primary_keys"] = context.primary_keys

        if context.foreign_keys:
            router_context["foreign_keys"] = [
                {
                    "column": fk.column_name,
                    "references": f"{fk.referenced_table}.{fk.referenced_column}",
                }
                for fk in context.foreign_keys
            ]

        if context.existing_rules:
            router_context["existing_rules"] = context.existing_rules

        return router_context

    def _extract_profiling(self, profile) -> dict[str, Any]:
        """Trích xuất profiling data cần thiết."""
        result = {}
        if profile.null_ratio is not None:
            result["null_ratio"] = profile.null_ratio
        if profile.distinct_ratio is not None:
            result["distinct_ratio"] = profile.distinct_ratio
        if profile.min_value is not None:
            result["min"] = profile.min_value
        if profile.max_value is not None:
            result["max"] = profile.max_value
        if profile.top_values:
            result["top_values"] = profile.top_values[:5]
        return result

    def _build_user_prompt(self, context: dict[str, Any]) -> str:
        """Build user prompt với serialized context.

        Args:
            context: Router context dict.

        Returns:
            User prompt string.
        """
        return json.dumps(context, indent=2, default=str)

    def _post_validate(
        self, full_context: TableContext, result: RouterResult
    ) -> RouterResult:
        """Post-validate các candidates từ router.

        - Loại bỏ candidates có column không hợp lệ
        - Loại bỏ duplicate candidates
        - Sắp xếp theo confidence giảm dần

        Args:
            full_context: Original table context để validate.
            result: Raw router result.

        Returns:
            RouterResult đã được validate.
        """
        valid_column_names = {col.name for col in full_context.columns}
        valid_candidates = []

        for candidate in result.candidates:
            # Validate columns tồn tại
            invalid_cols = [
                col for col in candidate.relevant_columns if col not in valid_column_names
            ]
            if invalid_cols:
                logger.warning(
                    f"Loại bỏ candidate {candidate.rule_type}: "
                    f"columns không hợp lệ {invalid_cols}"
                )
                continue

            # Loại bỏ duplicate columns trong candidate
            candidate.relevant_columns = list(set(candidate.relevant_columns))

            valid_candidates.append(candidate)

        # Loại bỏ exact duplicate candidates
        seen = set()
        unique_candidates = []
        for candidate in valid_candidates:
            key = (candidate.rule_type, tuple(sorted(candidate.relevant_columns)))
            if key not in seen:
                seen.add(key)
                unique_candidates.append(candidate)

        # Sắp xếp theo confidence giảm dần
        unique_candidates.sort(key=lambda c: c.confidence, reverse=True)

        return RouterResult(candidates=unique_candidates)


class RouterError(Exception):
    """Lỗi khi router thất bại."""

    pass
