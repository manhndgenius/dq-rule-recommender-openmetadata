"""APIs for running NT governance rules against OpenMetadata metadata."""

from __future__ import annotations

import math

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status

from backend.config.settings import settings
from backend.contracts.nt_execution import (
    CreateNTRunRequest,
    NTRunItemStatus,
    NTRunSummary,
    RetryNTRunRequest,
)
from backend.services.nt_run_service import nt_run_service
from backend.storage.nt_run_store import nt_run_store

router = APIRouter(
    prefix=f"{settings.api_prefix}/nt-runs",
    tags=["nt-runs"],
)


@router.post("", response_model=NTRunSummary, status_code=status.HTTP_202_ACCEPTED)
def create_nt_run(
    request: CreateNTRunRequest,
    background_tasks: BackgroundTasks,
) -> NTRunSummary:
    try:
        run = nt_run_service.prepare(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    background_tasks.add_task(nt_run_service.run, run.run_id)
    return nt_run_store.summary(run.run_id)


@router.get("/{run_id}", response_model=NTRunSummary)
def get_nt_run(run_id: str) -> NTRunSummary:
    summary = nt_run_store.summary(run_id)
    if not summary:
        raise HTTPException(status_code=404, detail="NT run not found")
    return summary


@router.get("/{run_id}/results")
def get_nt_run_results(
    run_id: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    item_status: NTRunItemStatus | None = Query(default=None, alias="status"),
    definition_name: str | None = None,
):
    if not nt_run_store.get(run_id):
        raise HTTPException(status_code=404, detail="NT run not found")
    items = nt_run_store.items(
        run_id,
        status=item_status,
        definition_name=definition_name,
    )
    start = (page - 1) * page_size
    return {
        "run_id": run_id,
        "page": page,
        "page_size": page_size,
        "total": len(items),
        "total_pages": math.ceil(len(items) / page_size) if items else 0,
        "items": items[start:start + page_size],
    }


@router.post(
    "/{run_id}/retry",
    response_model=NTRunSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
def retry_nt_run(
    run_id: str,
    request: RetryNTRunRequest,
    background_tasks: BackgroundTasks,
) -> NTRunSummary:
    try:
        retry_run = nt_run_service.retry(run_id, request)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    background_tasks.add_task(nt_run_service.run, retry_run.run_id)
    return nt_run_store.summary(retry_run.run_id)
