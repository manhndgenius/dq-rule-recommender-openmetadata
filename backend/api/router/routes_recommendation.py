"""API routes cho recommendation."""

import asyncio
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.contracts.candidate_rule import CandidateRule
from backend.contracts.generation import GenerationOptions, RuleEngine
from backend.engine.adapters.basic_adapter import BasicGenerationAdapter
from backend.engine.basic_engine import BasicRuleEngine
from backend.integrations.openmetadata.client import openmetadata_client
from backend.review.review_service import review_service
from backend.services.generation_service import (
    GenerationService,
    RulePersistenceError,
)
from backend.storage.rule_repository import rule_repository


router = APIRouter(prefix=settings.api_prefix, tags=["recommendation"])

basic_engine = BasicRuleEngine()


class GenerateRequest(BaseModel):
    """Request model cho generate recommendations."""

    table_name: str
    table_fqn: Optional[str] = None
    datasource_id: Optional[str] = "openmetadata"
    engines: List[str] = Field(default_factory=lambda: ["BASIC"])


@router.get("/rules/saved")
def get_saved_rules():
    """List persisted recommendations without starting generation."""
    try:
        return rule_repository.list_saved_rules()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL rule storage is unavailable",
        ) from exc


@router.post("/recommendations/generate")
def generate_recommendations(req: GenerateRequest):
    """Sinh recommendations cho một table.

    1. Lấy dữ liệu Schema & Profiling từ OpenMetadata
    2. Kích hoạt BasicRuleEngine (Heuristics)
    3. Trả về danh sách Candidate Rules cho Human Review
    """
    target = req.table_fqn or req.table_name
    if not req.engines:
        try:
            saved = rule_repository.get_rules(target)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail="PostgreSQL rule storage is unavailable",
            ) from exc
        return {
            "table_name": req.table_name,
            "table_fqn": target,
            "row_count": 0,
            "total_rules": len(saved),
            "generated_count": 0,
            "existing_count": sum(rule.get("status") == "APPLIED" for rule in saved),
            "duplicates_filtered": 0,
            "rules": saved,
        }

    context = openmetadata_client.get_table_context(target)
    table_fqn = req.table_fqn or getattr(context, "table_fqn", None) or target
    candidates: List[CandidateRule] = []
    reviewable_candidates: List[CandidateRule] = []
    duplicate_count = 0
    existing_count = 0

    # 1. Sinh Basic Rules (Heuristics dựa trên metrics)
    if "BASIC" in req.engines:
        service = GenerationService({
            RuleEngine.BASIC: BasicGenerationAdapter(rule_engine=basic_engine),
        })
        try:
            result = asyncio.run(service.generate(
                context=context,
                table_fqn=table_fqn,
                engine=RuleEngine.BASIC,
                options=GenerationOptions(),
                persist=True,
            ))
        except RulePersistenceError as exc:
            raise HTTPException(
                status_code=503,
                detail="Generated rules could not be persisted",
            ) from exc
        candidates = result.rules
        reviewable_candidates = result.reviewable_rules
        duplicate_count = result.duplicates_filtered
        existing_count = result.existing_count

    # Lưu vào review service (in-memory)
    # GenerationService already registered reviewable candidates.

    # Lưu vào database (PostgreSQL) - xóa cũ, ghi mới
    # GenerationService owns review registration and persistence.

    return {
        "table_name": req.table_name,
        "table_fqn": table_fqn,
        "row_count": context.row_count,
        "total_rules": len(candidates),
        "generated_count": len(reviewable_candidates),
        "existing_count": existing_count,
        "duplicates_filtered": duplicate_count,
        "rules": candidates,
    }
