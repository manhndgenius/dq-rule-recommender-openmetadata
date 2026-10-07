from backend.review.review_service import ReviewService, review_service


class EvaluationService:
    def __init__(self, reviews: ReviewService) -> None:
        self.reviews = reviews

    def get_summary(self) -> dict:
        candidates = self.reviews.list_candidates()
        total_reviewed = sum(rule.status != "DRAFT" for rule in candidates)
        counts = {
            status: sum(rule.status == status for rule in candidates)
            for status in ("ACCEPTED", "EDITED", "REJECTED")
        }
        denominator = total_reviewed or 1
        return {
            "total_candidates": len(candidates),
            "total_reviewed": total_reviewed,
            "accept_rate": counts["ACCEPTED"] / denominator if total_reviewed else 0.0,
            "edit_rate": counts["EDITED"] / denominator if total_reviewed else 0.0,
            "reject_rate": counts["REJECTED"] / denominator if total_reviewed else 0.0,
        }


evaluation_service = EvaluationService(review_service)
