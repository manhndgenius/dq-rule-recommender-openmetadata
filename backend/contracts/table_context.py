from typing import Any, List, Optional, Dict
from pydantic import BaseModel, Field
from enum import Enum


class ProfileSource(str, Enum):
    """Nguồn gốc của profile data."""
    OPENMETADATA = "OPENMETADATA"
    MOCK = "MOCK"
    UNKNOWN = "UNKNOWN"


class ProfileScope(str, Enum):
    """Phạm vi/profiling scope của data."""
    FULL_TABLE = "FULL_TABLE"
    SAMPLED = "SAMPLED"
    PARTITION = "PARTITION"
    UNKNOWN = "UNKNOWN"


class ColumnProfile(BaseModel):
    # Basic metrics (existing)
    row_count: int = 0
    null_count: int = 0
    null_ratio: float = 0.0
    distinct_count: int = 0
    distinct_ratio: float = 0.0
    min_value: Optional[Any] = None
    max_value: Optional[Any] = None
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    top_values: List[Dict[str, Any]] = Field(default_factory=list)

    # Statistical metrics from OpenMetadata profiler
    values_count: Optional[int] = None  # Số giá trị không NULL
    valid_count: Optional[int] = None   # Số giá trị hợp lệ
    mean: Optional[float] = None        # Giá trị trung bình
    median: Optional[float] = None      # Giá trị trung vị
    stddev: Optional[float] = None      # Độ lệch chuẩn
    q1: Optional[float] = None          # 25th percentile (firstQuartile)
    q3: Optional[float] = None          # 75th percentile (thirdQuartile)
    iqr: Optional[float] = None         # InterQuartileRange
    non_parametric_skew: Optional[float] = None  # Độ lệch tâm

    # Profile metadata
    profile_timestamp: Optional[int] = None  # Unix timestamp (ms) của lần profiling
    profile_source: ProfileSource = ProfileSource.UNKNOWN  # Nguồn profile
    profile_scope: ProfileScope = ProfileScope.UNKNOWN     # Phạm vi profiling

    def available_metrics(self) -> List[str]:
        """Trả về danh sách metric names có giá trị (không phải None)."""
        metrics = []
        if self.values_count is not None:
            metrics.append("values_count")
        if self.valid_count is not None:
            metrics.append("valid_count")
        if self.mean is not None:
            metrics.append("mean")
        if self.median is not None:
            metrics.append("median")
        if self.stddev is not None:
            metrics.append("stddev")
        if self.q1 is not None:
            metrics.append("q1")
        if self.q3 is not None:
            metrics.append("q3")
        if self.iqr is not None:
            metrics.append("iqr")
        if self.non_parametric_skew is not None:
            metrics.append("non_parametric_skew")
        return metrics

    def missing_metrics(self) -> List[str]:
        """Trả về danh sách metric names bị thiếu (None)."""
        all_metrics = ["values_count", "valid_count", "mean", "median", "stddev", "q1", "q3", "iqr", "non_parametric_skew"]
        return [m for m in all_metrics if getattr(self, m) is None]

class ColumnContext(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    description: Optional[str] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    profile: ColumnProfile = Field(default_factory=ColumnProfile)

class ForeignKeyInfo(BaseModel):
    """Thông tin về Foreign Key relationship."""
    column_name: str
    referenced_table: str
    referenced_column: str
    constraint_name: Optional[str] = None

class TableContext(BaseModel):
    datasource_id: str = "openmetadata"
    table_fqn: Optional[str] = None
    database_name: str
    schema_name: str
    table_name: str
    table_description: Optional[str] = None
    row_count: int = 0
    version: Optional[float] = None
    tier: Optional[str] = None
    domain: Optional[Any] = None
    owner: Optional[Dict[str, Any]] = None
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[ColumnContext] = Field(default_factory=list)
    existing_rules: List[Dict[str, Any]] = Field(default_factory=list)

    # Constraint metadata - bổ sung cho LLM
    primary_keys: List[str] = Field(default_factory=list)  # List of PK column names
    foreign_keys: List[ForeignKeyInfo] = Field(default_factory=list)  # List of FK info

    def get_pk_columns(self) -> List[str]:
        """Lấy danh sách primary key columns."""
        return [col.name for col in self.columns if col.is_primary_key]

    def get_fk_columns(self) -> List[str]:
        """Lấy danh sách foreign key columns."""
        return [col.name for col in self.columns if col.is_foreign_key]

