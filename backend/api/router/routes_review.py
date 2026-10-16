from fastapi import APIRouter, HTTPException

from backend.config.settings import settings
from backend.contracts.review import ReviewActionRequest
from backend.review.review_service import review_service
from backend.storage.generation_cache import generation_cache


router = APIRouter(prefix=settings.api_prefix, tags=["review"])


@router.post("/rules/{rule_id}/review")
def review_rule(rule_id: str, action_req: ReviewActionRequest):
    rule = review_service.review(rule_id, action_req)
    persisted = generation_cache.update_status(
        rule_id, action_req.action, action_req.edited_parameters
    )
    if rule is None and not persisted:
        raise HTTPException(status_code=404, detail="Không tìm thấy Rule với ID này")
    return {
        "message": f"Đã cập nhật rule {rule_id} thành {action_req.action}",
        "rule": rule or {"id": rule_id, "status": action_req.action},
    }
