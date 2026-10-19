"""Thread-safe in-memory state for NT application jobs."""

from threading import RLock
from typing import Dict, Iterable, List, Optional

from backend.contracts.batch_job import (
    JobItemStatus,
    JobStatus,
    TERMINAL_ITEM_STATUSES,
    utc_now,
)
from backend.contracts.nt_application_job import (
    CreateNtApplicationJobRequest,
    NtApplicationItem,
    NtApplicationJob,
    NtApplicationJobSummary,
)


class NtApplicationJobStore:
    def __init__(self) -> None:
        self._jobs: Dict[str, NtApplicationJob] = {}
        self._lock = RLock()

    def create(
        self, request: CreateNtApplicationJobRequest, tables: Iterable[str]
    ) -> NtApplicationJob:
        resolved_tables = list(dict.fromkeys(tables))
        job = NtApplicationJob(
            scope=request.scope,
            resolved_tables=resolved_tables,
            items=[NtApplicationItem(table_fqn=fqn) for fqn in resolved_tables],
        )
        with self._lock:
            self._jobs[job.job_id] = job
        return job.model_copy(deep=True)

    def get(self, job_id: str) -> Optional[NtApplicationJob]:
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

    def finish_item(
        self,
        job_id: str,
        item_id: str,
        status: JobItemStatus,
        created_count: int = 0,
        skipped_count: int = 0,
        failed_count: int = 0,
        errors: Optional[List[dict]] = None,
    ) -> None:
        with self._lock:
            item = self._item(job_id, item_id)
            item.status = status
            item.created_count = created_count
            item.skipped_count = skipped_count
            item.failed_count = failed_count
            item.errors = errors or []
            item.finished_at = utc_now()

    def finish_job(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs[job_id]
            failed = sum(i.status == JobItemStatus.FAILED for i in job.items)
            partial = sum(i.status == JobItemStatus.PARTIAL for i in job.items)
            successful = sum(i.status == JobItemStatus.SUCCESS for i in job.items)
            if failed == len(job.items):
                job.status = JobStatus.FAILED
            elif failed or partial:
                job.status = JobStatus.PARTIAL
            elif successful:
                job.status = JobStatus.SUCCESS
            else:
                job.status = JobStatus.FAILED
            job.finished_at = utc_now()

    def summary(self, job_id: str) -> Optional[NtApplicationJobSummary]:
        job = self.get(job_id)
        if not job:
            return None
        return NtApplicationJobSummary(
            job_id=job.job_id,
            scope=job.scope,
            status=job.status,
            total_tables=len(job.items),
            processed_tables=sum(i.status in TERMINAL_ITEM_STATUSES for i in job.items),
            successful_tables=sum(i.status == JobItemStatus.SUCCESS for i in job.items),
            partial_tables=sum(i.status == JobItemStatus.PARTIAL for i in job.items),
            failed_tables=sum(i.status == JobItemStatus.FAILED for i in job.items),
            created_count=sum(i.created_count for i in job.items),
            skipped_count=sum(i.skipped_count for i in job.items),
            failed_count=sum(i.failed_count for i in job.items),
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )

    def items(self, job_id: str) -> List[NtApplicationItem]:
        job = self.get(job_id)
        return job.items if job else []

    def _item(self, job_id: str, item_id: str) -> NtApplicationItem:
        for item in self._jobs[job_id].items:
            if item.item_id == item_id:
                return item
        raise KeyError(f"NT application item not found: {item_id}")


nt_application_job_store = NtApplicationJobStore()
