"""API routes cho recommendation."""

from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.config.settings import settings
from backend.contracts.candidate_rule import CandidateRule
from backend.engine.basic_engine import BasicRuleEngine
from backend.integrations.openmetadata.client import openmetadata_client
from backend.review.review_service import review_service


router = APIRouter(prefix=settings.api_prefix, tags=["recommendation"])

basic_engine = BasicRuleEngine()


class GenerateRequest(BaseModel):
    """Request model cho generate recommendations."""

    table_name: str
    datasource_id: Optional[str] = "openmetadata"
    engines: List[str] = Field(default_factory=lambda: ["BASIC"])


@router.post("/recommendations/generate")
def generate_recommendations(req: GenerateRequest):
    """Sinh recommendations cho một table.

    1. Lấy dữ liệu Schema & Profiling từ OpenMetadata
    2. Kích hoạt BasicRuleEngine (Heuristics)
    3. Trả về danh sách Candidate Rules cho Human Review
    """
    context = openmetadata_client.get_table_context(req.table_name)
    candidates: List[CandidateRule] = []

    # 1. Sinh Basic Rules (Heuristics dựa trên metrics)
    if "BASIC" in req.engines:
        candidates.extend(basic_engine.generate_candidates(context))

    # Lưu vào review service
    review_service.save_candidates(candidates)

    return {
        "table_name": req.table_name,
        "row_count": context.row_count,
        "total_rules": len(candidates),
        "rules": candidates,
    }
