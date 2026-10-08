"""Models cho router - phat hien cac loai advanced rule tien nang."""

from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from backend.contracts.rule_type import AdvancedRuleType


class RouterCandidate(BaseModel):
    """Mot candidate advanced rule duoc router phat hien."""

    rule_type: AdvancedRuleType
    """Loai rule co the ton tai trong bang nay."""

    subtype: Optional[str] = None
    """Subtype cho CONDITIONAL_DEPENDENCY: IN_SET | null"""

    relevant_columns: list[str] = Field(min_length=1, validation_alias="columns")
    """Cac cot lien quan den candidate rule nay. Alias: 'columns'"""

    confidence: float = Field(ge=0.0, le=1.0)
    """Diem confidence tu 0 den 1."""

    reason: str
    """Ly do co co so cho candidate nay."""

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)


class RouterResult(BaseModel):
    """Kết quả từ router chứa các candidates đã phát hiện."""

    candidates: list[RouterCandidate] = Field(default_factory=list)
    """Danh sách các loại rule. Có thể rỗng."""
