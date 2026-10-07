"""API routes cho advanced rules recommendation với SQL."""

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.contracts.table_context import TableContext, ColumnContext, ColumnProfile
from backend.engine.advanced_rule_service import AdvancedRuleService

router = APIRouter(prefix=settings.api_prefix, tags=["advanced-rules"])


class ColumnInput(BaseModel):
    """Input model cho một column."""

    name: str
    datatype: str = Field(alias="data_type")
    nullable: bool = True
    description: str | None = None
    profiling: dict[str, Any] | None = None

    class Config:
        populate_by_name = True


class AdvancedRulesRequest(BaseModel):
    """Request model cho advanced rules recommendation."""

    table_name: str
    table_description: str | None = None
    columns: list[ColumnInput] = Field(min_length=1)
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)


class RuleWithSQL(BaseModel):
    """Rule với SQL violation query."""

    rule_type: str
    table: str
    columns: list[str] = Field(default_factory=list)
    conditions: list[dict] = Field(default_factory=list)
    confidence: float
    reason: str = ""

    # SQL fields
    sql: str = ""
    violation_predicate: str = ""
    params: dict = Field(default_factory=dict)
    sql_error: str | None = None


class AdvancedRulesResponse(BaseModel):
    """Response model cho advanced rules recommendation với SQL."""

    table_name: str
    candidates: list[dict[str, Any]]
    rules: list[RuleWithSQL]

    # Statistics
    total_candidates: int = 0
    total_rules_generated: int = 0
    total_sql_mapped: int = 0
    total_sql_failed: int = 0

    errors: list[dict[str, Any]] = Field(default_factory=list)


@router.post("/advanced-rules/recommend", response_model=AdvancedRulesResponse)
async def recommend_advanced_rules(req: AdvancedRulesRequest) -> AdvancedRulesResponse:
    """Tạo advanced rule recommendations với SQL violation queries.

    Pipeline hoàn chỉnh:
    1. Router phát hiện candidates
    2. Generators tạo rules
    3. SQL Mapper chuyển rules thành SQL

    Args:
        req: Request chứa table metadata.

    Returns:
        AdvancedRulesResponse với rules và SQL violation queries.
    """
    # Build TableContext từ request
    columns = []
    for col_input in req.columns:
        profile = None
        if col_input.profiling:
            profile = ColumnProfile(**col_input.profiling)

        columns.append(ColumnContext(
            name=col_input.name,
            data_type=col_input.datatype,
            nullable=col_input.nullable,
            description=col_input.description,
            profile=profile or ColumnProfile(),
        ))

    context = TableContext(
        database_name="request",
        schema_name="request",
        table_name=req.table_name,
        table_description=req.table_description,
        columns=columns,
    )

    # Tạo service và chạy pipeline với SQL
    service = AdvancedRuleService(min_confidence=req.min_confidence)

    try:
        result = await service.recommend_with_sql(context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")

    # Build response
    return AdvancedRulesResponse(
        table_name=result.table_name,
        candidates=result.candidates,
        rules=[
            RuleWithSQL(
                rule_type=r.rule_type,
                table=r.table,
                columns=r.columns,
                conditions=r.conditions,
                confidence=r.confidence,
                reason=r.reason,
                sql=r.sql,
                violation_predicate=r.violation_predicate,
                params=r.params,
                sql_error=r.sql_error,
            )
            for r in result.rules
        ],
        total_candidates=result.total_candidates,
        total_rules_generated=result.total_rules_generated,
        total_sql_mapped=result.total_sql_mapped,
        total_sql_failed=result.total_sql_failed,
        errors=result.errors,
    )
