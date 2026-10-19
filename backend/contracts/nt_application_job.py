"""Contracts for applying the NT governance catalog to target tables."""

from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from backend.contracts.batch_job import JobItemStatus, JobStatus, utc_now
from backend.contracts.target_scope import TargetScope


class CreateNtApplicationJobRequest(BaseModel):
    scope: TargetScope


class NtApplicationItem(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid4()))
    table_fqn: str
    status: JobItemStatus = JobItemStatus.PENDING
    created_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    errors: List[Dict[str, Any]] = Field(default_factory=list)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class NtApplicationJob(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid4()))
    scope: TargetScope
    resolved_tables: List[str]
    items: List[NtApplicationItem]
    status: JobStatus = JobStatus.PENDING
    created_at: str = Field(default_factory=utc_now)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class NtApplicationJobSummary(BaseModel):
    job_id: str
    scope: TargetScope
    status: JobStatus
    total_tables: int
    processed_tables: int
    successful_tables: int
    partial_tables: int
    failed_tables: int
    created_count: int
    skipped_count: int
    failed_count: int
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
