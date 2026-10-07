"""Models cho generator - output là các concrete rules."""

from pydantic import BaseModel, ConfigDict, Field

from backend.contracts.rule_type import AdvancedRuleType


class GeneratedRule(BaseModel):
    """Một candidate rule cụ thể được generator tạo ra."""

    rule_type: AdvancedRuleType
    """Loại của rule này."""

    target_table: str
    """Bảng mà rule này áp dụng."""

    columns: list[str] = Field(min_length=1)
    """Các cột liên quan trong rule này."""

    # Structured conditions cho SQL Mapper
    conditions: list[dict] = Field(default_factory=list)
    """Danh sách các conditions theo output contract."""

    # Legacy text field (for display)
    condition: str = ""
    """Điều kiện của rule dưới dạng text (legacy)."""

    reason: str = ""
    """Giải thích tại sao rule này được tạo."""

    confidence: float = Field(ge=0.0, le=1.0, default=0.8)
    """Điểm confidence từ 0 đến 1."""

    evidence: list[str] = Field(default_factory=list)
    """Danh sách bằng chứng hỗ trợ rule này."""

    model_config = ConfigDict(use_enum_values=True)


class GeneratorResult(BaseModel):
    """Kết quả từ generator chứa các rules đã tạo."""

    rules: list[GeneratedRule] = Field(default_factory=list)
    """Danh sách các rules. Có thể rỗng nếu không tìm thấy rule hợp lệ."""
