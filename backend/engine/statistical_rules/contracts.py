"""
Statistical Rules DTOs — Simplified v2.

Chỉ gồm:
- PreFilterResult: kết quả hard filter cho mỗi cột (0-3 eligible pairs)
- LLMReviewInput/Output: LLM payload
- StatisticalRuleCandidate: final output
- RecommendationResponse: API response
"""

from __future__ import annotations

import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class ThresholdStatus(str, Enum):
    PENDING_THRESHOLD = "PENDING_THRESHOLD"
    READY = "READY"
    ALREADY_EXISTS = "ALREADY_EXISTS"


class LLMSuggestion(str, Enum):
    RECOMMEND = "RECOMMEND"
    SKIP = "SKIP"
    UNCERTAIN = "UNCERTAIN"


# ---------------------------------------------------------------------------
# Pre-filter Result
# ---------------------------------------------------------------------------

class FilteredRule(BaseModel):
    """Một rule bị lọc kèm lý do."""
    rule_type: str
    reason_code: str  # e.g. "MISSING_OR_INVALID_PROFILE_METRIC"


class PreFilterResult(BaseModel):
    """Kết quả pre-filter cho một cột."""
    column_name: str
    eligible_rules: List[str] = Field(default_factory=list)  # e.g. ["columnValueMeanToBeBetween"]
    filtered_rules: List[FilteredRule] = Field(default_factory=list)
    reason_codes: List[str] = Field(default_factory=list)  # e.g. ["NUMERIC", "VALID_PROFILE"]


# ---------------------------------------------------------------------------
# LLM Review - Grouped Input/Output
# ---------------------------------------------------------------------------

class LLMColumnReview(BaseModel):
    """
    Một cột cần review - gộp profile + rules.
    Dùng cho cả eligible columns và non-eligible columns (schema context).
    """
    name: str
    datatype: str = ""
    description: str = ""
    is_pk: bool = False
    is_fk: bool = False
    # Profile - chỉ eligible columns mới có
    profile: Optional[Dict[str, Any]] = None
    # Rules cần review - chỉ eligible columns mới có
    rules: List[str] = Field(default_factory=list)  # e.g. ["mean", "median", "stddev"]


class LLMSuggestionContext(BaseModel):
    """
    Full context gửi lên LLM.
    - table: table info
    - columns: all columns (schema + eligible profile/rules)
    - existing_rules: list of existing rule types
    """
    table: Dict[str, str]  # fqn, name, description
    columns: List[LLMColumnReview]
    existing_rules: List[str] = Field(default_factory=list)


class LLMSuggestionDecision(BaseModel):
    """
    Một decision từ LLM.
    Chỉ cần candidate_id + decision + reason.
    Backend tự parse column/rule từ candidate_id.
    """
    candidate_id: str  # "column::ruleAlias" e.g. "healthcare_expense::mean"
    decision: LLMSuggestion
    reason: str


class LLMSuggestionResult(BaseModel):
    """Kết quả từ LLM."""
    decisions: List[LLMSuggestionDecision]


# ---------------------------------------------------------------------------
# Final Candidate
# ---------------------------------------------------------------------------

class StatisticalProfilePoint(BaseModel):
    """Một điểm metric trong lịch sử profile, dùng trực tiếp cho chart ở FE."""
    timestamp: int
    value: float


class StatisticalRuleCandidate(BaseModel):
    """Một rule candidate cuối cùng."""
    id: str = Field(default_factory=lambda: f"stat_{uuid.uuid4().hex[:8]}")
    column: str
    rule_type: str
    decision: LLMSuggestion
    threshold_status: ThresholdStatus = ThresholdStatus.PENDING_THRESHOLD
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    evidence: Dict[str, Any] = Field(default_factory=dict)
    profile_metric: Optional[str] = None
    profile_history: List[StatisticalProfilePoint] = Field(default_factory=list)


class DiagnosticEntry(BaseModel):
    """Diagnostic cho một cột."""
    column: str
    status: str  # e.g. "FILTERED", "MISSING_PROFILE"
    reason_code: str = ""  # Chỉ 1 code, không lặp
    reason_codes: List[str] = Field(default_factory=list)
    message: str = ""


# ---------------------------------------------------------------------------
# API Response
# ---------------------------------------------------------------------------

class SummaryStats(BaseModel):
    columns_scanned: int = 0
    eligible_columns: int = 0
    eligible_pairs: int = 0
    filtered_pairs: int = 0
    llm_calls: int = 0
    recommended_pairs: int = 0
    skipped_pairs: int = 0
    uncertain_pairs: int = 0


class StatisticalRecommendationResponse(BaseModel):
    """Response cho API endpoint."""
    table_fqn: str
    table_name: str
    profile_timestamp: Optional[int] = None
    summary: SummaryStats
    recommendations: List[StatisticalRuleCandidate] = Field(default_factory=list)
    skipped: List[StatisticalRuleCandidate] = Field(default_factory=list)
    uncertain: List[StatisticalRuleCandidate] = Field(default_factory=list)
    filtered: List[DiagnosticEntry] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
