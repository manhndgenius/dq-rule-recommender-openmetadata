from backend.contracts.candidate_rule import CandidateRule
from backend.contracts.table_context import TableContext


class TypeValidator:
    def validate(self, candidate: CandidateRule, context: TableContext) -> list[str]:
        """Return type compatibility messages; detailed rules are added per rule type."""
        return []
