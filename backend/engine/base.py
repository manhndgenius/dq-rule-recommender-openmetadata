from abc import ABC, abstractmethod
from typing import List
from backend.contracts.table_context import TableContext
from backend.contracts.candidate_rule import CandidateRule

class BaseRuleEngine(ABC):
    """
    Interface chung bắt buộc cho cả Basic Rule Engine và Advanced Rule Engine (LLD Mục 10).
    Input: TableContext -> Output: List[CandidateRule]
    """
    @abstractmethod
    def generate_candidates(self, context: TableContext) -> List[CandidateRule]:
        pass
