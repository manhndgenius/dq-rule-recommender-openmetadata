from fastapi import APIRouter

from backend.config.settings import settings
from backend.evaluation.evaluation_service import evaluation_service


router = APIRouter(prefix=settings.api_prefix, tags=["evaluation"])


@router.get("/evaluation/summary")
def get_evaluation_summary():
    return evaluation_service.get_summary()
