"""Run server-side NT Test Case application jobs."""

import logging

from backend.api.router.routes_test_cases import create_default_test_cases
from backend.contracts.batch_job import JobItemStatus
from backend.storage.nt_application_job_store import (
    NtApplicationJobStore,
    nt_application_job_store,
)
from backend.services.heavy_job_coordinator import heavy_job_coordinator


logger = logging.getLogger(__name__)


class NtApplicationJobRunner:
    def __init__(self, store: NtApplicationJobStore = nt_application_job_store):
        self.store = store

    async def run(self, job_id: str) -> None:
        async with heavy_job_coordinator.slot(job_id, "NT_APPLICATION"):
            await self._run_sequentially(job_id)

    async def _run_sequentially(self, job_id: str) -> None:
        job = self.store.get(job_id)
        if not job:
            return
        self.store.start_job(job_id)
        try:
            # Deliberately sequential: each table can create up to 15 entities
            # in OpenMetadata and should not cause a write burst.
            for item in job.items:
                await self._run_item(job_id, item.item_id, item.table_fqn)
        finally:
            self.store.finish_job(job_id)

    async def _run_item(self, job_id: str, item_id: str, table_fqn: str) -> None:
        self.store.start_item(job_id, item_id)
        try:
            result = await create_default_test_cases(table_fqn)
            created = int(result.get("created_count", 0))
            skipped = int(result.get("skipped_count", 0))
            failed = int(result.get("failed_count", 0))
            if result.get("success") is True:
                status = JobItemStatus.SUCCESS
            elif created or skipped:
                status = JobItemStatus.PARTIAL
            else:
                status = JobItemStatus.FAILED
            errors = result.get("failed", [])
            if result.get("error"):
                errors = [*errors, {"message": result["error"]}]
            self.store.finish_item(
                job_id,
                item_id,
                status,
                created_count=created,
                skipped_count=skipped,
                failed_count=failed,
                errors=errors,
            )
        except Exception as exc:
            logger.exception("NT application failed for %s", table_fqn)
            self.store.finish_item(
                job_id,
                item_id,
                JobItemStatus.FAILED,
                failed_count=15,
                errors=[{"message": str(exc)}],
            )


nt_application_job_runner = NtApplicationJobRunner()
