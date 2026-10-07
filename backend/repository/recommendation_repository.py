from typing import Iterable

from backend.contracts.candidate_rule import CandidateRule


class RecommendationRepository:
    def save(self, candidates: Iterable[CandidateRule]) -> None:
        raise NotImplementedError
