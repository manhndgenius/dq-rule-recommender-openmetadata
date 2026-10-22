import logging
from fastapi import APIRouter, HTTPException

from backend.config.settings import settings
from backend.contracts.review import ReviewActionRequest
from backend.storage.rule_repository import rule_repository
from backend.storage.generation_cache import generation_cache
from backend.review.review_service import review_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix=settings.api_prefix, tags=["review"])


@router.post("/rules/{rule_id}/review")
def review_rule(rule_id: str, action_req: ReviewActionRequest):
    persisted = False
    rule = None
    try:
        persisted = rule_repository.update_status(
            rule_id,
            action_req.action,
            action_req.edited_parameters,
        )
        rule = rule_repository.get_rule(rule_id) if persisted else None
        if rule:
            generation_cache.update_status(
                rule_id, action_req.action, action_req.edited_parameters
            )
            review_service.review(rule_id, action_req)
            return {
                "message": f"Đã cập nhật rule {rule_id} thành {action_req.action}",
                "rule": rule,
            }
    except Exception as exc:
        logger.warning(f"Database update failed for rule {rule_id}: {exc}")
        # In-memory fallback
        in_memory_rule = review_service.review(rule_id, action_req)
        if in_memory_rule:
            generation_cache.update_status(
                rule_id, action_req.action, action_req.edited_parameters
            )
            return {
                "message": f"Đã cập nhật rule {rule_id} thành {action_req.action} (in-memory)",
                "rule": in_memory_rule.model_dump(),
            }
        raise HTTPException(
            status_code=503,
            detail=f"PostgreSQL rule storage is unavailable: {exc}",
        ) from exc

    if not persisted:
        raise HTTPException(status_code=404, detail="Không tìm thấy Rule với ID này")
    return {
        "message": f"Đã cập nhật rule {rule_id} thành {action_req.action}",
        "rule": rule,
    }
