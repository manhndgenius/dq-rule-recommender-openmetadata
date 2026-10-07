"""Models cho router - phát hiện các loại advanced rule tiềm năng."""

from pydantic import BaseModel, ConfigDict, Field

from backend.contracts.rule_type import AdvancedRuleType


class RouterCandidate(BaseModel):
    """Một candidate advanced rule được router phát hiện."""

    rule_type: AdvancedRuleType
    """Loại rule có thể tồn tại trong bảng này."""

    relevant_columns: list[str] = Field(min_length=1, validation_alias="columns")
    """Các cột liên quan đến candidate rule này. Alias: 'columns'"""

    confidence: float = Field(ge=0.0, le=1.0)
    """Điểm confidence từ 0 đến 1."""

    reason: str
    """Lý do có cơ sở cho candidate này."""

    model_config = ConfigDict(use_enum_values=True, populate_by_name=True)


class RouterResult(BaseModel):
    """Kết quả từ router chứa các candidates đã phát hiện."""

    candidates: list[RouterCandidate] = Field(default_factory=list)
    """Danh sách các loại rule. Có thể rỗng."""
