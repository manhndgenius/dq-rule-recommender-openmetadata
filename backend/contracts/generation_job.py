"""Contracts for schema/database-wide recommendation jobs."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from backend.contracts.generation import GenerationOptions, RuleEngine


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ScopeType(str, Enum):
    TABLE = "TABLE"
    SCHEMA = "SCHEMA"
    DATABASE = "DATABASE"


class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class JobItemStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


TERMINAL_ITEM_STATUSES = {
    JobItemStatus.SUCCESS,
    JobItemStatus.PARTIAL,
    JobItemStatus.FAILED,
    JobItemStatus.SKIPPED,
}


class GenerationScope(BaseModel):
    type: ScopeType
    target_fqn: str = Field(min_length=1)


class BulkConcurrency(BaseModel):
    metadata: int = Field(default=4, ge=1, le=8)
    basic: int = Field(default=8, ge=1, le=16)
    statistical: int = Field(default=2, ge=1, le=4)
    advanced: int = Field(default=2, ge=1, le=4)


class CreateGenerationJobRequest(BaseModel):
    scope: GenerationScope
    engines: List[RuleEngine] = Field(min_length=1)
    options: GenerationOptions = Field(default_factory=GenerationOptions)
    concurrency: BulkConcurrency = Field(default_factory=BulkConcurrency)

    @model_validator(mode="after")
    def deduplicate_engines(self):
        self.engines = list(dict.fromkeys(self.engines))
        return self


class PreviewResponse(BaseModel):
    scope: GenerationScope
    total_tables: int
    tables: List[str]
    total_items: int
    estimated_llm_calls: Dict[str, int] = Field(default_factory=dict)


class JobItem(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid4()))
    table_fqn: str
    engine: RuleEngine
    status: JobItemStatus = JobItemStatus.PENDING
    generated_count: int = 0
    existing_count: int = 0
    duplicates_filtered: int = 0
    llm_calls: int = 0
    warnings: List[str] = Field(default_factory=list)
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class GenerationJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    source_job_id: Optional[str] = None
    scope: GenerationScope
    engines: List[RuleEngine]
    options: GenerationOptions
    concurrency: BulkConcurrency
    resolved_tables: List[str] = Field(default_factory=list)
    items: List[JobItem] = Field(default_factory=list)
    status: JobStatus = JobStatus.PENDING
    created_at: str = Field(default_factory=utc_now)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class JobSummary(BaseModel):
    job_id: str
    source_job_id: Optional[str] = None
    scope: GenerationScope
    engines: List[RuleEngine]
    status: JobStatus
    total_tables: int
    total_items: int
    processed_items: int
    successful_items: int
    partial_items: int
    failed_items: int
    skipped_items: int
    generated_rules: Dict[str, int]
    llm_calls: Dict[str, int]
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class RetryJobRequest(BaseModel):
    table_fqns: Optional[List[str]] = None
    engines: Optional[List[RuleEngine]] = None
    include_partial: bool = True
