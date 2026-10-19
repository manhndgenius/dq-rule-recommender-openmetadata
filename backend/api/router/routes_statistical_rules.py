"""API routes cho statistical rules recommendation."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.contracts.generation import GenerationOptions, RuleEngine
from backend.engine.adapters.statistical_adapter import StatisticalGenerationAdapter
from backend.engine.statistical_rules import StatisticalRulesService, statistical_rules_service
from backend.engine.statistical_rules.profile_history import (
    enrich_recommendation_profile_history,
)
from backend.integrations.openmetadata.client import openmetadata_client
from backend.services.generation_service import (
    GenerationService,
    RulePersistenceError,
)

router = APIRouter(prefix=settings.api_prefix, tags=["statistical-rules"])


class GenerateStatisticalRequest(BaseModel):
    """Request model cho statistical rules generation."""
    table_name: str
    table_fqn: Optional[str] = None
    datasource_id: Optional[str] = "openmetadata"
    use_llm: bool = Field(default=True, description="Whether to use LLM review")


@router.post("/recommendations/statistical/generate")
async def generate_statistical_recommendations(req: GenerateStatisticalRequest):
    """
    Sinh statistical rules (Mean/Median/StdDev) cho một table.

    1. Load table context từ OpenMetadata
    2. Pre-filter để tìm eligible (column, rule_type) pairs
    3. (Optional) Gửi eligible pairs + table schema cho LLM review
    4. Gắn 4 profile gần nhất vào các recommendations để FE hiển thị
    5. Trả về recommendations chờ threshold
    """
    # Resolve the canonical FQN once. TableContext currently stores database,
    # schema and table but not the service name required by profile APIs.
    target = req.table_fqn or req.table_name
    catalog = openmetadata_client.get_catalog_table(target)
    table_fqn = req.table_fqn or catalog.get("fqn") or target

    # Get table context from OM
    context = openmetadata_client.get_table_context(target)

    if not context:
        raise HTTPException(status_code=404, detail=f"Table not found: {req.table_name}")

    # Run recommendation
    service = GenerationService({
        RuleEngine.STATISTICAL: StatisticalGenerationAdapter(),
    })
    try:
        result = await service.generate(
            context=context,
            table_fqn=table_fqn,
            engine=RuleEngine.STATISTICAL,
            options=GenerationOptions(use_llm=req.use_llm),
            persist=True,
        )
    except RulePersistenceError as exc:
        raise HTTPException(
            status_code=503,
            detail="Generated rules could not be persisted",
        ) from exc

    return {
        "table_fqn": table_fqn,
        "table_name": context.table_name,
        "profile_timestamp": result.metadata.get("profile_timestamp"),
        "summary": result.metadata.get("summary", {}),
        "recommendations": [rule.model_dump() for rule in result.rules],
        "skipped": result.metadata.get("skipped", []),
        "uncertain": result.metadata.get("uncertain", []),
        "filtered": result.metadata.get("filtered", []),
        "warnings": result.warnings,
    }
