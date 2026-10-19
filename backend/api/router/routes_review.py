from fastapi import APIRouter, HTTPException

from backend.config.settings import settings
from backend.contracts.review import ReviewActionRequest
from backend.storage.rule_repository import rule_repository


router = APIRouter(prefix=settings.api_prefix, tags=["review"])


@router.post("/rules/{rule_id}/review")
def review_rule(rule_id: str, action_req: ReviewActionRequest):
    try:
        persisted = rule_repository.update_status(
            rule_id,
            action_req.action,
            action_req.edited_parameters,
        )
        rule = rule_repository.get_rule(rule_id) if persisted else None
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL rule storage is unavailable",
        ) from exc

    if not persisted:
        raise HTTPException(status_code=404, detail="Không tìm thấy Rule với ID này")
    return {
        "message": f"Đã cập nhật rule {rule_id} thành {action_req.action}",
        "rule": rule,
    }
