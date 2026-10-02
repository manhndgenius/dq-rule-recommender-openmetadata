from typing import Any, List, Optional, Dict
from pydantic import BaseModel, Field

class ColumnProfile(BaseModel):
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

class ColumnContext(BaseModel):
    name: str
    data_type: str
    nullable: bool = True
    description: Optional[str] = None
    is_primary_key: bool = False
    is_foreign_key: bool = False
    profile: ColumnProfile = Field(default_factory=ColumnProfile)

class TableContext(BaseModel):
    datasource_id: str = "openmetadata"
    database_name: str
    schema_name: str
    table_name: str
    table_description: Optional[str] = None
    row_count: int = 0
    tier: Optional[str] = "Tier.Tier1"
    domain: Optional[str] = "E-Commerce"
    owner: Optional[Dict[str, Any]] = None
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[ColumnContext] = Field(default_factory=list)
    existing_rules: List[Dict[str, Any]] = Field(default_factory=list)

