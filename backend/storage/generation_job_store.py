"""Thread-safe in-memory storage for background recommendation jobs."""

from __future__ import annotations

from threading import RLock
from typing import Dict, Iterable, List, Optional

from backend.contracts.generation import RuleEngine
from backend.contracts.generation_job import (
    CreateGenerationJobRequest,
    GenerationJob,
    JobItem,
    JobItemStatus,
    JobStatus,
    JobSummary,
    TERMINAL_ITEM_STATUSES,
    utc_now,
)


class GenerationJobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, GenerationJob] = {}
        self._lock = RLock()

    def create(
        self,
        request: CreateGenerationJobRequest,
        tables: Iterable[str],
        source_job_id: str | None = None,
        item_pairs: Iterable[tuple[str, RuleEngine]] | None = None,
    ) -> GenerationJob:
        resolved_tables = list(dict.fromkeys(tables))
        pairs = list(item_pairs or (
            (table_fqn, engine)
            for table_fqn in resolved_tables
            for engine in request.engines
        ))
        job = GenerationJob(
            source_job_id=source_job_id,
            scope=request.scope,
            engines=list(dict.fromkeys(engine for _, engine in pairs)),
            options=request.options,
            concurrency=request.concurrency,
            resolved_tables=resolved_tables,
            items=[
                JobItem(table_fqn=table_fqn, engine=engine)
                for table_fqn, engine in pairs
            ],
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job.model_copy(deep=True)

    def get(self, job_id: str) -> Optional[GenerationJob]:
        with self._lock:
            job = self._jobs.get(job_id)
            return job.model_copy(deep=True) if job else None

    def start_job(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            job.status = JobStatus.RUNNING
            job.started_at = job.started_at or utc_now()

    def start_item(self, job_id: str, item_id: str) -> None:
        with self._lock:
            item = self._item(job_id, item_id)
            item.status = JobItemStatus.RUNNING
            item.started_at = utc_now()
            item.finished_at = None
            item.errors = []

    def finish_item(
        self,
        job_id: str,
        item_id: str,
        status: JobItemStatus,
        generated_count: int = 0,
        existing_count: int = 0,
        duplicates_filtered: int = 0,
        llm_calls: int = 0,
        warnings: Optional[List[str]] = None,
        errors: Optional[List[dict]] = None,
    ) -> None:
        with self._lock:
            item = self._item(job_id, item_id)
            item.status = status
            item.generated_count = generated_count
            item.existing_count = existing_count
            item.duplicates_filtered = duplicates_filtered
            item.llm_calls = llm_calls
            item.warnings = warnings or []
            item.errors = errors or []
            item.finished_at = utc_now()

    def finish_job(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            failed = sum(item.status == JobItemStatus.FAILED for item in job.items)
            partial = sum(item.status == JobItemStatus.PARTIAL for item in job.items)
            successful = sum(item.status == JobItemStatus.SUCCESS for item in job.items)
            skipped = sum(item.status == JobItemStatus.SKIPPED for item in job.items)
            if failed == len(job.items):
                job.status = JobStatus.FAILED
            elif failed or partial:
                job.status = JobStatus.PARTIAL
            elif successful or skipped:
                job.status = JobStatus.SUCCESS
            else:
                job.status = JobStatus.FAILED
            job.finished_at = utc_now()

    def summary(self, job_id: str) -> Optional[JobSummary]:
        job = self.get(job_id)
        if not job:
            return None
        counts = {
            status: sum(item.status == status for item in job.items)
            for status in JobItemStatus
        }
        generated = {engine.value: 0 for engine in job.engines}
        llm_calls = {engine.value: 0 for engine in job.engines}
        for item in job.items:
            generated[item.engine.value] = generated.get(item.engine.value, 0) + item.generated_count
            llm_calls[item.engine.value] = llm_calls.get(item.engine.value, 0) + item.llm_calls
        return JobSummary(
            job_id=job.job_id,
            source_job_id=job.source_job_id,
            scope=job.scope,
            engines=job.engines,
            status=job.status,
            total_tables=len(job.resolved_tables),
            total_items=len(job.items),
            processed_items=sum(
                item.status in TERMINAL_ITEM_STATUSES for item in job.items
            ),
            successful_items=counts[JobItemStatus.SUCCESS],
            partial_items=counts[JobItemStatus.PARTIAL],
            failed_items=counts[JobItemStatus.FAILED],
            skipped_items=counts[JobItemStatus.SKIPPED],
            generated_rules=generated,
            llm_calls=llm_calls,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )

    def items(
        self,
        job_id: str,
        engine: RuleEngine | None = None,
        status: JobItemStatus | None = None,
        table_fqn: str | None = None,
    ) -> List[JobItem]:
        job = self.get(job_id)
        if not job:
            return []
        return [
            item for item in job.items
            if (engine is None or item.engine == engine)
            and (status is None or item.status == status)
            and (table_fqn is None or item.table_fqn == table_fqn)
        ]

    def _item(self, job_id: str, item_id: str) -> JobItem:
        job = self._jobs[job_id]
        for item in job.items:
            if item.item_id == item_id:
                return item
        raise KeyError(f"Job item not found: {item_id}")


generation_job_store = GenerationJobStore()
