from backend.contracts.candidate_rule import CandidateRule


class ConflictValidator:
    def validate(self, candidate: CandidateRule, candidates: list[CandidateRule]) -> list[str]:
        """Return explicit conflict messages; detailed comparisons are rule-specific."""
        return []
