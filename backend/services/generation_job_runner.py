"""Asynchronous runner for bulk recommendation jobs."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Dict, List

from backend.contracts.generation import RuleEngine
from backend.contracts.generation_job import JobItem, JobItemStatus
from backend.engine.adapters import (
    AdvancedGenerationAdapter,
    BasicGenerationAdapter,
)
from backend.integrations.openmetadata.client import openmetadata_client
from backend.services.generation_service import GenerationService
from backend.services.heavy_job_coordinator import heavy_job_coordinator
from backend.storage.generation_job_store import (
    GenerationJobStore,
    generation_job_store,
)

logger = logging.getLogger(__name__)


class GenerationJobRunner:
    def __init__(self, store: GenerationJobStore = generation_job_store):
        self.store = store
        self.generation_service = GenerationService({
            RuleEngine.BASIC: BasicGenerationAdapter(),
            RuleEngine.ADVANCED: AdvancedGenerationAdapter(),
        })

    async def run(self, job_id: str) -> None:
        async with heavy_job_coordinator.slot(job_id, "GENERATION"):
            await self._run_sequentially(job_id)

    async def _run_sequentially(self, job_id: str) -> None:
        job = self.store.get(job_id)
        if not job:
            return
        self.store.start_job(job_id)
        grouped: Dict[str, List[JobItem]] = defaultdict(list)
        for item in job.items:
            if item.status == JobItemStatus.PENDING:
                grouped[item.table_fqn].append(item)

        try:
            # Strictly process one table at a time. Within a table, engines are
            # also processed sequentially in the order requested by the user.
            for table_fqn, items in grouped.items():
                await self._run_table(
                    job_id,
                    table_fqn,
                    items,
                    job.options,
                )
        finally:
            self.store.finish_job(job_id)

    async def _run_table(
        self,
        job_id: str,
        table_fqn: str,
        items: List[JobItem],
        options,
    ) -> None:
        try:
            context = await asyncio.to_thread(
                openmetadata_client.get_table_context,
                table_fqn,
            )
        except Exception as exc:
            for item in items:
                self.store.start_item(job_id, item.item_id)
                self.store.finish_item(
                    job_id,
                    item.item_id,
                    JobItemStatus.FAILED,
                    errors=[{"step": "context", "message": str(exc)}],
                )
            return

        for item in items:
            await self._run_item(
                job_id,
                item,
                context,
                options,
            )

    async def _run_item(
        self,
        job_id: str,
        item: JobItem,
        context,
        options,
    ) -> None:
        self.store.start_item(job_id, item.item_id)
        try:
            result = await self.generation_service.generate(
                context=context,
                table_fqn=item.table_fqn,
                engine=item.engine,
                options=options,
                persist=True,
            )
            status = JobItemStatus(result.status)
            self.store.finish_item(
                job_id,
                item.item_id,
                status,
                generated_count=result.generated_count,
                existing_count=result.existing_count,
                duplicates_filtered=result.duplicates_filtered,
                llm_calls=result.llm_calls,
                warnings=result.warnings,
                errors=[error.model_dump() for error in result.errors],
            )
        except Exception as exc:
            logger.exception(
                "Bulk generation failed for %s/%s", item.table_fqn, item.engine.value
            )
            self.store.finish_item(
                job_id,
                item.item_id,
                JobItemStatus.FAILED,
                errors=[{"step": "generate", "message": str(exc)}],
            )


generation_job_runner = GenerationJobRunner()
