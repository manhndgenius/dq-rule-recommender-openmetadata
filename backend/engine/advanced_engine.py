from typing import List

from backend.contracts.candidate_rule import CandidateRule
from backend.contracts.table_context import TableContext
from backend.engine.base import BaseRuleEngine


class AdvancedRuleEngine(BaseRuleEngine):
    """Current deterministic advanced-rule adapter, ready to be replaced by LLM output."""

    
