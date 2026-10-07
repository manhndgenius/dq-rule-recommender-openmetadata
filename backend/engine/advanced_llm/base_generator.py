"""Base Generator interface cho các specialized generators."""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from typing import Any

from backend.contracts.table_context import TableContext
from backend.contracts.advanced_rule_router import RouterCandidate
from backend.contracts.advanced_rule import GeneratorResult, GeneratedRule
from backend.engine.advanced_llm.client import LLMClient

logger = logging.getLogger(__name__)


class BaseRuleGenerator(ABC):
    """Abstract base class cho các specialized rule generators."""

    # Subclasses nên override nếu cần custom prompt file
    DEFAULT_PROMPT_FILE: str = ""

    def __init__(self, llm_client: LLMClient, prompt_file: str | None = None):
        """Khởi tạo generator.

        Args:
            llm_client: LLM client để gọi API.
            prompt_file: Tên file prompt trong prompts/ (mặc định dùng DEFAULT_PROMPT_FILE).
        """
        self._llm = llm_client
        self._prompt_file = prompt_file or self.DEFAULT_PROMPT_FILE

    @abstractmethod
    async def generate(
        self,
        context: TableContext,
        candidate: RouterCandidate,
    ) -> GeneratorResult:
        """Tạo các concrete rules từ router candidate.

        Args:
            context: Full table context.
            candidate: Router candidate chứa rule type và columns.

        Returns:
            GeneratorResult chứa các generated rules.
        """
        pass

    def _build_generator_context(
        self,
        context: TableContext,
        candidate: RouterCandidate,
    ) -> dict[str, Any]:
        """Build context cho generator với các columns liên quan.

        Args:
            context: Full table context.
            candidate: Router candidate.

        Returns:
            Compact context dict cho generator.
        """
        relevant_col_names = set(candidate.relevant_columns)
        relevant_columns = [
            col for col in context.columns if col.name in relevant_col_names
        ]

        columns_data = []
        for col in relevant_columns:
            col_data = {
                "name": col.name,
                "datatype": col.data_type,
                "nullable": col.nullable,
            }
            if col.description:
                col_data["description"] = col.description
            if col.profile:
                col_data["profiling"] = self._extract_profiling(col.profile)
            columns_data.append(col_data)

        generator_context = {
            "table": {
                "name": context.table_name,
                "description": context.table_description or "",
            },
            "columns": columns_data,
            "rule_type": candidate.rule_type,
            "reason": candidate.reason,
        }

        return generator_context

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

    def _validate_rules(
        self,
        rules: list[GeneratedRule],
        valid_column_names: set[str],
    ) -> list[GeneratedRule]:
        """Validate và filter rules.

        - Loại bỏ rules có column không hợp lệ
        - Loại bỏ rules không có condition (condition text hoặc conditions list rỗng)
        - Loại bỏ duplicate rules

        Args:
            rules: Danh sách rules cần validate.
            valid_column_names: Tập hợp tên columns hợp lệ.

        Returns:
            Danh sách rules đã được validate.
        """
        valid_rules = []

        for rule in rules:
            # Validate columns
            invalid_cols = [
                col for col in rule.columns if col not in valid_column_names
            ]
            if invalid_cols:
                logger.warning(
                    f"Loại bỏ rule: columns không hợp lệ {invalid_cols}"
                )
                continue

            # Validate condition - chấp nhận cả condition (string) và conditions (list)
            has_condition_text = rule.condition and rule.condition.strip()
            has_conditions_list = rule.conditions and len(rule.conditions) > 0

            if not has_condition_text and not has_conditions_list:
                logger.warning("Loại bỏ rule: không có condition hoặc conditions")
                continue

            valid_rules.append(rule)

        # Loại bỏ duplicates dựa trên columns và condition
        seen = set()
        unique_rules = []
        for rule in valid_rules:
            # Unique key bao gồm cả condition text và conditions list
            cond_key = rule.condition.lower().strip() if rule.condition else ""
            # Convert conditions list to hashable form
            if rule.conditions:
                import json
                cond_list_key = json.dumps(rule.conditions, sort_keys=True)
            else:
                cond_list_key = ""

            key = (
                rule.rule_type,
                tuple(sorted(rule.columns)),
                cond_key,
                cond_list_key,
            )
            if key not in seen:
                seen.add(key)
                unique_rules.append(rule)

        return unique_rules
