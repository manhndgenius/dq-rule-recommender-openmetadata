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
    StatisticalGenerationAdapter,
)
from backend.integrations.openmetadata.client import openmetadata_client
from backend.services.generation_service import GenerationService
from backend.storage.generation_job_store import (
    GenerationJobStore,
    generation_job_store,
)

logger = logging.getLogger(__name__)


class GenerationJobRunner:
    # Global caps apply across all concurrently running jobs.
    _global_metadata = asyncio.Semaphore(4)
    _global_engine = {
        RuleEngine.BASIC: asyncio.Semaphore(8),
        RuleEngine.STATISTICAL: asyncio.Semaphore(2),
        RuleEngine.ADVANCED: asyncio.Semaphore(2),
    }

    def __init__(self, store: GenerationJobStore = generation_job_store):
        self.store = store
        self.generation_service = GenerationService({
            RuleEngine.BASIC: BasicGenerationAdapter(),
            RuleEngine.STATISTICAL: StatisticalGenerationAdapter(),
            RuleEngine.ADVANCED: AdvancedGenerationAdapter(),
        })

    async def run(self, job_id: str) -> None:
        job = self.store.get(job_id)
        if not job:
            return
        self.store.start_job(job_id)
        local_metadata = asyncio.Semaphore(job.concurrency.metadata)
        local_engine = {
            RuleEngine.BASIC: asyncio.Semaphore(job.concurrency.basic),
            RuleEngine.STATISTICAL: asyncio.Semaphore(job.concurrency.statistical),
            RuleEngine.ADVANCED: asyncio.Semaphore(job.concurrency.advanced),
        }
        grouped: Dict[str, List[JobItem]] = defaultdict(list)
        for item in job.items:
            if item.status == JobItemStatus.PENDING:
                grouped[item.table_fqn].append(item)

        try:
            await asyncio.gather(*(
                self._run_table(
                    job_id,
                    table_fqn,
                    items,
                    job.options,
                    local_metadata,
                    local_engine,
                )
                for table_fqn, items in grouped.items()
            ))
        finally:
            self.store.finish_job(job_id)

    async def _run_table(
        self,
        job_id: str,
        table_fqn: str,
        items: List[JobItem],
        options,
        local_metadata: asyncio.Semaphore,
        local_engine: Dict[RuleEngine, asyncio.Semaphore],
    ) -> None:
        try:
            async with self._global_metadata, local_metadata:
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

        await asyncio.gather(*(
            self._run_item(
                job_id,
                item,
                context,
                options,
                local_engine[item.engine],
            )
            for item in items
        ))

    async def _run_item(
        self,
        job_id: str,
        item: JobItem,
        context,
        options,
        local_semaphore: asyncio.Semaphore,
    ) -> None:
        self.store.start_item(job_id, item.item_id)
        try:
            async with self._global_engine[item.engine], local_semaphore:
                result = await self.generation_service.generate(
                    context=context,
                    table_fqn=item.table_fqn,
                    engine=item.engine,
                    options=options,
                    persist=False,
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
