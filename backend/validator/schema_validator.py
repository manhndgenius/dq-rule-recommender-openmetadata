from backend.contracts.candidate_rule import CandidateRule
from backend.contracts.table_context import TableContext


class SchemaValidator:
    def validate(self, candidate: CandidateRule, context: TableContext) -> list[str]:
        known_columns = {column.name for column in context.columns}
        missing = set(candidate.target_columns) - known_columns
        return [f"Unknown target column: {name}" for name in sorted(missing)]
