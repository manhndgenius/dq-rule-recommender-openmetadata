from typing import Dict, Iterable, Optional

from backend.contracts.candidate_rule import CandidateRule
from backend.contracts.review import ReviewActionRequest


class ReviewService:
    def __init__(self) -> None:
        self._candidates: Dict[str, CandidateRule] = {}

    def save_candidates(self, candidates: Iterable[CandidateRule]) -> None:
        for candidate in candidates:
            self._candidates[candidate.id] = candidate

    def review(
        self, rule_id: str, request: ReviewActionRequest
    ) -> Optional[CandidateRule]:
        rule = self._candidates.get(rule_id)
        if rule is None:
            return None
        rule.status = request.action
        if request.action == "EDITED" and request.edited_parameters:
            rule.edited_parameters = request.edited_parameters
        return rule

    def list_candidates(self) -> list[CandidateRule]:
        return list(self._candidates.values())


review_service = ReviewService()
