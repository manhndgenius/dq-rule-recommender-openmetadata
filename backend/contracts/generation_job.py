"""Contracts for schema/database-wide recommendation jobs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from backend.contracts.generation import GenerationOptions, RuleEngine
from backend.contracts.batch_job import (
    JobItemStatus,
    JobStatus,
    TERMINAL_ITEM_STATUSES,
    utc_now,
)
from backend.contracts.target_scope import TargetScope


class BulkConcurrency(BaseModel):
    # Kept in the request contract for backward compatibility. Bulk jobs are
    # intentionally executed one table and one engine at a time.
    metadata: int = Field(default=1, ge=1, le=8)
    basic: int = Field(default=1, ge=1, le=16)
    advanced: int = Field(default=1, ge=1, le=4)


class CreateGenerationJobRequest(BaseModel):
    scope: TargetScope
    engines: List[RuleEngine] = Field(default_factory=lambda: [RuleEngine.BASIC], min_length=1)
    options: GenerationOptions = Field(default_factory=GenerationOptions)
    concurrency: BulkConcurrency = Field(default_factory=BulkConcurrency)

    @model_validator(mode="after")
    def validate_go_live_engines(self):
        self.engines = list(dict.fromkeys(self.engines))
        enabled = {RuleEngine.BASIC, RuleEngine.ADVANCED}
        unsupported = [engine.value for engine in self.engines if engine not in enabled]
        if unsupported:
            raise ValueError(
                "Only the BASIC and ADVANCED rule engines are enabled for go-live; "
                "unsupported engines: "
                + ", ".join(unsupported)
            )
        return self


class PreviewResponse(BaseModel):
    scope: TargetScope
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
    scope: TargetScope
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
    scope: TargetScope
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
