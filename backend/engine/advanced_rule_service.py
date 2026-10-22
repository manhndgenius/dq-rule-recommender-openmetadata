"""Advanced Rule Service - orchestration của router và các generators."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Iterable

from pydantic import BaseModel, Field

from backend.contracts.table_context import TableContext
from backend.contracts.advanced_rule_router import RouterResult
from backend.contracts.advanced_rule import GeneratedRule, GeneratorResult
from backend.contracts.rule_type import AdvancedRuleType
from backend.engine.advanced_llm import (
    LLMClient,
    AdvancedRuleRouter,
    CrossColumnGenerator,
    ConditionalDependencyGenerator,
    TemporalGenerator,
    GeneratorError,
)
from backend.engine.sql_mapper import map_advanced_rule_to_sql, MapperError
from backend.engine.sql_mapper.dialect_transpiler import (
    CANONICAL_SQL_DIALECT,
    SQLDialectError,
    transpile_postgres_sql,
)
from backend.engine.sql_mapper.sql_renderer import render_sql_literal, SQLRenderError

if TYPE_CHECKING:
    from backend.engine.advanced_llm.router import RouterError

logger = logging.getLogger(__name__)


class RuleWithSQL(BaseModel):
    """Generated rule kèm SQL violation query."""

    rule_type: str
    table: str
    columns: list[str] = Field(default_factory=list)
    conditions: list[dict] = Field(default_factory=list)
    confidence: float = 0.8
    reason: str = ""

    # SQL fields
    sql: str = ""
    rendered_sql: str = ""
    violation_predicate: str = ""
    params: dict = Field(default_factory=dict)
    sql_error: str | None = None


class AdvancedRuleWithSQLResult(BaseModel):
    """Kết quả của pipeline với SQL."""

    table_name: str
    candidates: list[dict] = Field(default_factory=list)
    rules: list[RuleWithSQL] = Field(default_factory=list)
    errors: list[dict] = Field(default_factory=list)

    total_candidates: int = 0
    total_rules_generated: int = 0
    total_sql_mapped: int = 0
    total_sql_failed: int = 0
    canonical_dialect: str = CANONICAL_SQL_DIALECT
    target_dialect: str = CANONICAL_SQL_DIALECT

# Generator registry theo rule type
GENERATOR_REGISTRY = {
    AdvancedRuleType.CROSS_COLUMN: CrossColumnGenerator,
    AdvancedRuleType.CONDITIONAL_DEPENDENCY: ConditionalDependencyGenerator,
    AdvancedRuleType.TEMPORAL: TemporalGenerator,
}


class AdvancedRuleService:
    """Service orchestrate router và các generators để tạo advanced rules."""

    def __init__(
        self,
        llm_client: LLMClient | None = None,
        min_confidence: float = 0.75,
    ):
        """Khởi tạo Advanced Rule Service.

        Args:
            llm_client: LLM client. Tự tạo mới nếu không truyền.
            min_confidence: Confidence threshold để chọn candidates.
        """
        self._llm = llm_client or LLMClient()
        self._router = AdvancedRuleRouter(self._llm)
        self._min_confidence = min_confidence
        self._generators = {}

    def _get_generator(self, rule_type: AdvancedRuleType):
        """Lấy generator theo rule type (cached)."""
        if rule_type not in self._generators:
            generator_class = GENERATOR_REGISTRY.get(rule_type)
            if generator_class:
                self._generators[rule_type] = generator_class(self._llm)
        return self._generators.get(rule_type)

    async def recommend(
        self,
        context: TableContext,
        allowed_types: Iterable[str] | None = None,
    ) -> tuple[RouterResult, list[GeneratedRule]]:
        """Tạo advanced rule recommendations cho một table.

        Args:
            context: Table context với metadata và profiling.

        Returns:
            Tuple của (router_result, generated_rules).
        """
        logger.info(f"Bắt đầu recommend cho table: {context.table_name}")

        # 1. Router phát hiện candidates
        try:
            router_result = await self._router.route(context)
        except Exception as e:
            logger.error(f"Router thất bại: {e}")
            raise

        # 2. Filter candidates theo confidence threshold
        allowed_type_values = {
            item.value if isinstance(item, AdvancedRuleType) else str(item)
            for item in (allowed_types or [])
        }
        selected = [
            c for c in router_result.candidates
            if c.confidence >= self._min_confidence
            and (
                not allowed_type_values
                or getattr(c.rule_type, "value", str(c.rule_type)) in allowed_type_values
            )
        ]

        logger.info(
            f"Router trả về {len(router_result.candidates)} candidates, "
            f"chọn {len(selected)} candidates (threshold={self._min_confidence})"
        )

        # 3. Gọi generators cho từng selected candidate (sequential)
        all_rules = []
        warnings = []

        for candidate in selected:
            generator = self._get_generator(candidate.rule_type)
            if not generator:
                logger.warning(f"Không tìm thấy generator cho {candidate.rule_type}")
                warnings.append({
                    "rule_type": candidate.rule_type,
                    "error": "GENERATOR_NOT_FOUND",
                })
                continue

            try:
                result: GeneratorResult = await generator.generate(context, candidate)
                all_rules.extend(result.rules)
                logger.debug(
                    f"Generator {candidate.rule_type} tạo {len(result.rules)} rules"
                )
            except GeneratorError as e:
                logger.error(f"Generator {candidate.rule_type} thất bại: {e}")
                warnings.append({
                    "rule_type": candidate.rule_type,
                    "error": "GENERATOR_FAILED",
                })
                # Không raise - tiếp tục với các generators khác

        # 4. Deduplicate rules
        final_rules = self._deduplicate(all_rules)

        logger.info(
            f"Tạo được {len(final_rules)} rules từ {len(all_rules)} rules "
            f"(sau khi deduplicate)"
        )

        return router_result, final_rules

    async def recommend_with_sql(
        self,
        context: TableContext,
        include_failed_sql: bool = True,
        allowed_types: Iterable[str] | None = None,
    ) -> AdvancedRuleWithSQLResult:
        """Tạo advanced rules với SQL violation queries.

        Pipeline hoàn chỉnh:
        1. Router phát hiện candidates
        2. Generators tạo rules
        3. SQL Mapper chuyển rules thành SQL

        Args:
            context: Table context với metadata và profiling.
            include_failed_sql: Include rules mà SQL mapping thất bại.

        Returns:
            AdvancedRuleWithSQLResult với rules và SQL.
        """
        logger.info(f"Pipeline recommend_with_sql cho table: {context.table_name}")

        target_dialect = context.sql_dialect or CANONICAL_SQL_DIALECT
        result = AdvancedRuleWithSQLResult(
            table_name=context.table_name,
            target_dialect=target_dialect,
        )

        # 1. Router phát hiện candidates
        try:
            router_result, generated_rules = await self.recommend(
                context,
                allowed_types=allowed_types,
            )
        except Exception as e:
            logger.error(f"Pipeline thất bại ở bước recommend: {e}")
            result.errors.append({"step": "recommend", "error": str(e)})
            return result

        allowed_type_values = {
            item.value if isinstance(item, AdvancedRuleType) else str(item)
            for item in (allowed_types or [])
        }
        if allowed_type_values:
            router_result.candidates = [
                candidate
                for candidate in router_result.candidates
                if getattr(candidate.rule_type, "value", str(candidate.rule_type))
                in allowed_type_values
            ]
            generated_rules = [
                rule
                for rule in generated_rules
                if str(rule.rule_type) in allowed_type_values
            ]

        # Store candidates info
        result.candidates = [
            {
                "rule_type": c.rule_type,
                "columns": c.relevant_columns,
                "confidence": c.confidence,
                "reason": c.reason,
            }
            for c in router_result.candidates
        ]
        result.total_candidates = len(router_result.candidates)

        # 2. Map rules sang SQL
        for rule in generated_rules:
            rule_with_sql = RuleWithSQL(
                rule_type=rule.rule_type,
                table=rule.target_table,
                columns=rule.columns,
                conditions=rule.conditions,
                confidence=rule.confidence,
                reason=rule.reason,
            )

            # Skip if no conditions
            if not rule.conditions:
                logger.warning(f"Rule không có conditions, skip SQL mapping")
                rule_with_sql.sql_error = "NO_CONDITIONS"
                if include_failed_sql:
                    result.rules.append(rule_with_sql)
                result.total_rules_generated += 1
                continue

            # Map to SQL
            try:
                rule_dict = {
                    "rule_type": rule.rule_type,
                    "table": rule.target_table,
                    "columns": rule.columns,
                    "conditions": rule.conditions,
                }
                sql_result = map_advanced_rule_to_sql(rule_dict)

                rule_with_sql.sql = sql_result["sql"]
                rule_with_sql.violation_predicate = sql_result["violation_predicate"]
                rule_with_sql.params = sql_result["params"]
                try:
                    canonical_sql = render_sql_literal(
                        rule_with_sql.sql,
                        rule_with_sql.params,
                    )
                    rule_with_sql.rendered_sql = transpile_postgres_sql(
                        canonical_sql,
                        target_dialect,
                    )
                except (SQLRenderError, SQLDialectError) as e:
                    # Keep canonical SQL for review, but mark the rule invalid
                    # so it cannot be published for the target database.
                    logger.warning(f"SQL rendering/transpilation failed for rule: {e}")
                    rule_with_sql.sql_error = str(e)
                result.total_sql_mapped += 1

            except MapperError as e:
                logger.warning(f"SQL mapping failed cho rule: {e}")
                rule_with_sql.sql_error = str(e)
            except Exception as e:
                logger.error(f"Lỗi không xác định khi map SQL: {e}")
                rule_with_sql.sql_error = str(e)
            if not rule_with_sql.sql_error or include_failed_sql:
                result.rules.append(rule_with_sql)
            result.total_rules_generated += 1

        result.total_sql_failed = sum(
            1 for r in result.rules if r.sql_error
        )

        logger.info(
            f"Pipeline hoàn thành: {result.total_rules_generated} rules, "
            f"{result.total_sql_mapped} SQL mapped, {result.total_sql_failed} failed"
        )

        return result

    def _deduplicate(self, rules: list[GeneratedRule]) -> list[GeneratedRule]:
        """Loại bỏ duplicate rules.

        Args:
            rules: Danh sách rules cần deduplicate.

        Returns:
            Danh sách rules đã deduplicate.
        """
        seen = set()
        unique_rules = []

        for rule in rules:
            # Normalize key: rule_type + sorted columns + normalized condition
            # Sử dụng conditions list nếu có, fallback sang condition text
            if rule.conditions:
                import json
                cond_key = json.dumps(rule.conditions, sort_keys=True)
            else:
                cond_key = rule.condition.lower().strip() if rule.condition else ""

            key = (
                rule.rule_type,
                tuple(sorted(rule.columns)),
                cond_key,
            )
            if key not in seen:
                seen.add(key)
                unique_rules.append(rule)

        return unique_rules
