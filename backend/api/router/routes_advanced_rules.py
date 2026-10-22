"""API routes cho advanced rules recommendation voi SQL."""

from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.contracts.generation import GenerationOptions, RuleEngine
from backend.contracts.table_context import TableContext, ColumnContext, ColumnProfile
from backend.engine.adapters.advanced_adapter import AdvancedGenerationAdapter
from backend.engine.advanced_rule_service import AdvancedRuleService
from backend.engine.sql_mapper.sql_renderer import render_sql_literal, SQLRenderError
from backend.engine.sql_mapper.dialect_transpiler import resolve_sql_dialect
from backend.integrations.openmetadata.client import openmetadata_client
from backend.storage.json_storage import json_storage
from backend.storage.rule_repository import rule_repository
from backend.services.generation_service import (
    GenerationService,
    RulePersistenceError,
)

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
    table_fqn: str | None = None
    table_description: str | None = None
    columns: list[ColumnInput] = Field(min_length=1)
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    advanced_types: list[str] | None = None


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
    rendered_sql: str = ""
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

    fqn_parts = (req.table_fqn or "").split(".")
    service_name = fqn_parts[0] if len(fqn_parts) >= 4 else ""
    service_type = (
        openmetadata_client.get_database_service_type(service_name)
        if service_name
        else "Postgres"
    )
    sql_dialect = resolve_sql_dialect(service_type) or "unsupported"
    context = TableContext(
        table_fqn=req.table_fqn,
        database_service_type=service_type,
        sql_dialect=sql_dialect,
        database_name=fqn_parts[-3] if len(fqn_parts) >= 4 else "request",
        schema_name=fqn_parts[-2] if len(fqn_parts) >= 4 else "request",
        table_name=req.table_name,
        table_description=req.table_description,
        columns=columns,
    )

    # Tao service va chay pipeline voi SQL
    service = GenerationService({
        RuleEngine.ADVANCED: AdvancedGenerationAdapter(),
    })

    try:
        result = await service.generate(
            context=context,
            table_fqn=req.table_fqn or req.table_name,
            engine=RuleEngine.ADVANCED,
            options=GenerationOptions(
                min_confidence=req.min_confidence,
                advanced_types=req.advanced_types,
            ),
            persist=True,
        )
    except RulePersistenceError as exc:
        raise HTTPException(
            status_code=503,
            detail="Generated rules could not be persisted",
        ) from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline failed: {str(e)}")

    # Build response
    rules_list = [
        RuleWithSQL(
            rule_type=r.rule_type,
            table=req.table_name,
            columns=r.target_columns,
            conditions=r.conditions,
            confidence=r.confidence,
            reason=r.reason,
            sql=r.sql or "",
            rendered_sql=r.rendered_sql or "",
            violation_predicate=r.violation_predicate or "",
            params=r.params,
            sql_error=r.validation_message if r.validation_status == "INVALID" else None,
        )
        for r in result.rules
    ]

    response = AdvancedRulesResponse(
        table_name=result.table_name,
        candidates=result.metadata.get("candidates", []),
        rules=rules_list,
        total_candidates=result.metadata.get("total_candidates", 0),
        total_rules_generated=result.metadata.get("total_rules_generated", 0),
        total_sql_mapped=result.metadata.get("total_sql_mapped", 0),
        total_sql_failed=result.metadata.get("total_sql_failed", 0),
        errors=[error.model_dump() for error in result.errors],
    )

    return response


@router.get("/advanced-rules/saved")
def get_saved_advanced_rules(
    table_name: Optional[str] = None,
    table_fqn: Optional[str] = None,
):
    """Load Advanced Rules from PostgreSQL with a legacy JSON fallback."""
    rules = []
    info = None
    target = table_fqn or table_name
    if target:
        try:
            rules = rule_repository.get_rules(target, engine="ADVANCED")
            info = {"storage": "postgresql", "table_fqn": target}
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="PostgreSQL rule storage is unavailable",
            ) from exc
    if not rules:
        # Compatibility fallback for data generated before PostgreSQL storage.
        rules = json_storage.get_advanced_rules(table_name)
        info = json_storage.get_file_info()

    # Backward compatibility for files created before `rendered_sql` existed.
    for rule in rules or []:
        if rule.get("rendered_sql") or not rule.get("sql"):
            continue
        try:
            rule["rendered_sql"] = render_sql_literal(
                rule["sql"],
                rule.get("params", {}),
            )
        except SQLRenderError:
            rule["rendered_sql"] = rule["sql"]

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
