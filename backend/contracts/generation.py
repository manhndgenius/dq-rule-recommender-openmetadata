"""Shared contracts for table-level rule generation engines."""

from enum import Enum
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

from backend.contracts.candidate_rule import CandidateRule


class RuleEngine(str, Enum):
    BASIC = "BASIC"
    STATISTICAL = "STATISTICAL"
    ADVANCED = "ADVANCED"


class GenerationOptions(BaseModel):
    use_llm: bool = True
    min_confidence: float = Field(default=0.6, ge=0.0, le=1.0)
    advanced_types: Optional[List[str]] = None
    profile_history_limit: int = Field(default=4, ge=0, le=20)


class GenerationError(BaseModel):
    step: str
    message: str
    code: Optional[str] = None


class EngineGenerationResult(BaseModel):
    engine: RuleEngine
    table_fqn: str
    table_name: str
    status: Literal["SUCCESS", "PARTIAL", "FAILED", "SKIPPED"] = "SUCCESS"
    rules: List[CandidateRule] = Field(default_factory=list)
    reviewable_rules: List[CandidateRule] = Field(default_factory=list)
    generated_count: int = 0
    existing_count: int = 0
    duplicates_filtered: int = 0
    llm_calls: int = 0
    warnings: List[str] = Field(default_factory=list)
    errors: List[GenerationError] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
