from typing import Iterable, List

from backend.contracts.candidate_rule import CandidateRule
from backend.contracts.table_context import TableContext
from backend.engine.base import BaseRuleEngine


class RecommendationOrchestrator:
    def __init__(self, engines: Iterable[BaseRuleEngine]):
        self.engines = list(engines)

    def generate(self, context: TableContext) -> List[CandidateRule]:
        candidates: List[CandidateRule] = []
        for engine in self.engines:
            candidates.extend(engine.generate_candidates(context))
        return candidates
