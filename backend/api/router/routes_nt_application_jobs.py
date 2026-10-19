"""Server-side jobs that apply the NT governance catalog to target tables."""

import math

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from backend.api.router.routes_target_scopes import resolve_scope_or_422
from backend.config.settings import settings
from backend.contracts.nt_application_job import (
    CreateNtApplicationJobRequest,
    NtApplicationJobSummary,
)
from backend.services.nt_application_job_runner import nt_application_job_runner
from backend.storage.nt_application_job_store import nt_application_job_store


router = APIRouter(
    prefix=f"{settings.api_prefix}/nt-application-jobs",
    tags=["nt-application-jobs"],
)


@router.post("/preview")
async def preview_nt_application_job(request: CreateNtApplicationJobRequest):
    tables = await resolve_scope_or_422(request.scope)
    return {
        "scope": request.scope,
        "total_tables": len(tables),
        "tables": tables,
        "definitions_per_table": 15,
        "maximum_test_cases": len(tables) * 15,
    }


@router.post("", response_model=NtApplicationJobSummary, status_code=status.HTTP_202_ACCEPTED)
async def create_nt_application_job(
    request: CreateNtApplicationJobRequest,
    background_tasks: BackgroundTasks,
) -> NtApplicationJobSummary:
    tables = await resolve_scope_or_422(request.scope)
    job = nt_application_job_store.create(request, tables)
    background_tasks.add_task(nt_application_job_runner.run, job.job_id)
    return nt_application_job_store.summary(job.job_id)


@router.get("/{job_id}", response_model=NtApplicationJobSummary)
def get_nt_application_job(job_id: str) -> NtApplicationJobSummary:
    summary = nt_application_job_store.summary(job_id)
    if not summary:
        raise HTTPException(status_code=404, detail="NT application job not found")
    return summary


@router.get("/{job_id}/results")
def get_nt_application_job_results(
    job_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
):
    if not nt_application_job_store.get(job_id):
        raise HTTPException(status_code=404, detail="NT application job not found")
    items = nt_application_job_store.items(job_id)
    start = (page - 1) * page_size
    return {
        "job_id": job_id,
        "page": page,
        "page_size": page_size,
        "total": len(items),
        "total_pages": math.ceil(len(items) / page_size) if items else 0,
        "items": items[start:start + page_size],
    }
