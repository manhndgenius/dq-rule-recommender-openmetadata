import json

from backend.contracts.candidate_rule import CandidateRule


class DuplicateValidator:
    @staticmethod
    def canonical_key(candidate: CandidateRule) -> tuple:
        return (
            candidate.rule_type,
            tuple(sorted(candidate.target_columns)),
            json.dumps(candidate.parameters, sort_keys=True, default=str),
            (candidate.expression or "").strip(),
        )
