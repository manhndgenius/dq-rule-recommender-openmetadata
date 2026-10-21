"""Bulk recommendation job APIs."""

from __future__ import annotations

import math

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from backend.config.settings import settings
from backend.contracts.generation import RuleEngine
from backend.contracts.generation_job import (
    CreateGenerationJobRequest,
    JobItemStatus,
    JobSummary,
    PreviewResponse,
    RetryJobRequest,
)
from backend.services.generation_job_runner import generation_job_runner
from backend.api.router.routes_target_scopes import resolve_scope_or_422
from backend.storage.generation_job_store import generation_job_store

router = APIRouter(
    prefix=f"{settings.api_prefix}/recommendation-jobs",
    tags=["recommendation-jobs"],
)


async def _resolve_tables(request: CreateGenerationJobRequest) -> list[str]:
    return await resolve_scope_or_422(request.scope)


@router.post("/preview", response_model=PreviewResponse)
async def preview_generation_job(
    request: CreateGenerationJobRequest,
) -> PreviewResponse:
    tables = await _resolve_tables(request)
    estimates = {
        engine.value: (
            len(tables) * 4 if engine == RuleEngine.ADVANCED else 0
        )
        for engine in request.engines
    }
    return PreviewResponse(
        scope=request.scope,
        total_tables=len(tables),
        tables=tables,
        total_items=len(tables) * len(request.engines),
        estimated_llm_calls=estimates,
    )


@router.post("", response_model=JobSummary, status_code=status.HTTP_202_ACCEPTED)
async def create_generation_job(
    request: CreateGenerationJobRequest,
    background_tasks: BackgroundTasks,
) -> JobSummary:
    tables = await _resolve_tables(request)
    job = generation_job_store.create(request, tables)
    background_tasks.add_task(generation_job_runner.run, job.job_id)
    return generation_job_store.summary(job.job_id)


@router.get("/{job_id}", response_model=JobSummary)
def get_generation_job(job_id: str) -> JobSummary:
    summary = generation_job_store.summary(job_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Generation job not found")
    return summary


@router.get("/{job_id}/results")
def get_generation_job_results(
    job_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    engine: RuleEngine | None = None,
    item_status: JobItemStatus | None = Query(default=None, alias="status"),
    table_fqn: str | None = None,
):
    if not generation_job_store.get(job_id):
        raise HTTPException(status_code=404, detail="Generation job not found")
    items = generation_job_store.items(
        job_id,
        engine=engine,
        status=item_status,
        table_fqn=table_fqn,
    )
    start = (page - 1) * page_size
    return {
        "job_id": job_id,
        "page": page,
        "page_size": page_size,
        "total": len(items),
        "total_pages": math.ceil(len(items) / page_size) if items else 0,
        "items": items[start:start + page_size],
    }


@router.post(
    "/{job_id}/retry",
    response_model=JobSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_generation_job(
    job_id: str,
    request: RetryJobRequest,
    background_tasks: BackgroundTasks,
) -> JobSummary:
    source = generation_job_store.get(job_id)
    if not source:
        raise HTTPException(status_code=404, detail="Generation job not found")

    retry_statuses = {JobItemStatus.FAILED}
    if request.include_partial:
        retry_statuses.add(JobItemStatus.PARTIAL)
    table_filter = set(request.table_fqns or [])
    engine_filter = set(request.engines or [])
    pairs = [
        (item.table_fqn, item.engine)
        for item in source.items
        if item.status in retry_statuses
        and (not table_filter or item.table_fqn in table_filter)
        and (not engine_filter or item.engine in engine_filter)
    ]
    if not pairs:
        raise HTTPException(status_code=400, detail="No failed job items matched retry filters")

    cloned_request = CreateGenerationJobRequest(
        scope=source.scope,
        engines=list(dict.fromkeys(engine for _, engine in pairs)),
        options=source.options,
        concurrency=source.concurrency,
    )
    retry_job = generation_job_store.create(
        cloned_request,
        tables=list(dict.fromkeys(table for table, _ in pairs)),
        source_job_id=source.job_id,
        item_pairs=pairs,
    )
    background_tasks.add_task(generation_job_runner.run, retry_job.job_id)
    return generation_job_store.summary(retry_job.job_id)
