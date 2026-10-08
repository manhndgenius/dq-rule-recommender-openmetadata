"""API routes cho advanced rules recommendation voi SQL."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.contracts.table_context import TableContext, ColumnContext, ColumnProfile
from backend.engine.advanced_rule_service import AdvancedRuleService
from backend.storage.json_storage import json_storage

router = APIRouter(prefix=settings.api_prefix, tags=["advanced-rules"])


def _generate_short_description(rule_type: str, columns: list, reason: str) -> str:
    """Tao description ngan gon cho rule."""
    if not columns:
        cols_str = "cac cot"
    else:
        cols_str = ", ".join(columns[:3])
        if len(columns) > 3:
            cols_str += "..."

    if rule_type == "TEMPORAL":
        return f"Temporal Constraint: thu tu thoi gian giua {cols_str}"
    elif rule_type == "CROSS_COLUMN":
        return f"Cross-Column: rang buoc giua {cols_str}"
    elif rule_type == "CONDITIONAL_DEPENDENCY":
        return f"Conditional Dependency: {cols_str}"
    else:
        if reason:
            return reason[:80].rsplit(' ', 1)[0] + "..."
        return f"{rule_type} Rule: {cols_str}"


class ColumnInput(BaseModel):
    """Input model cho mot column."""

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
    """Rule voi SQL violation query."""

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
    """Response model cho advanced rules recommendation voi SQL."""

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
    """Tao advanced rule recommendations voi SQL violation queries."""

    # Build TableContext tu request
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

    # Tao service va chay pipeline voi SQL
    service = AdvancedRuleService(min_confidence=req.min_confidence)

    try:
        result = await service.recommend_with_sql(context)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")

    # Build response
    rules_list = [
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
    ]

    response = AdvancedRulesResponse(
        table_name=result.table_name,
        candidates=result.candidates,
        rules=rules_list,
        total_candidates=result.total_candidates,
        total_rules_generated=result.total_rules_generated,
        total_sql_mapped=result.total_sql_mapped,
        total_sql_failed=result.total_sql_failed,
        errors=result.errors,
    )

    # Luu vao file JSON - ghi de
    if result.rules:
        rules_data = []
        for idx, r in enumerate(result.rules):
            description = _generate_short_description(r.rule_type, r.columns, r.reason)
            rules_data.append({
                'id': f"{r.rule_type}_adv_{idx + 1}",
                'rule_type': r.rule_type,
                'description': description,
                'target_columns': r.columns,
                'columns': r.columns,
                'parameters': {},
                'expression': None,
                'engine': 'ADVANCED',
                'confidence': r.confidence,
                'reason': r.reason,
                'evidence': {},
                'validation_status': 'VALID',
                'validation_message': None,
                'status': 'DRAFT',
                'edited_parameters': None,
                'sql': r.sql,
                'violation_predicate': r.violation_predicate,
                'params': r.params,
                'conditions': r.conditions,
            })
        try:
            json_storage.save_advanced_rules(req.table_name, rules_data)
        except Exception as e:
            import logging
            logging.warning(f"Failed to save advanced rules to JSON: {e}")

    return response


@router.get("/advanced-rules/saved")
def get_saved_advanced_rules(table_name: Optional[str] = None):
    """Lay Advanced Rules da luu tu file JSON."""
    rules = json_storage.get_advanced_rules(table_name)
    info = json_storage.get_file_info()

    return {
        "has_rules": rules is not None and len(rules) > 0,
        "file_info": info,
        "rules": rules or [],
        "total": len(rules) if rules else 0
    }


@router.delete("/advanced-rules/saved")
def delete_saved_advanced_rules():
    """Xoa file luu tru Advanced Rules."""
    success = json_storage.delete_advanced_rules()
    return {
        "success": success,
        "message": "Da xoa file luu tru" if success else "Khong the xoa file"
    }
