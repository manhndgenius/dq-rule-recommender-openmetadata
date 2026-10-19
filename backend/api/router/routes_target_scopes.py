"""Preview endpoints for target scopes shared by DQ batch operations."""

import asyncio

from fastapi import APIRouter, HTTPException

from backend.config.settings import settings
from backend.contracts.target_scope import TargetPreviewRequest, TargetPreviewResponse
from backend.services.scope_resolver import ScopeResolutionError, scope_resolver


router = APIRouter(
    prefix=f"{settings.api_prefix}/target-scopes",
    tags=["target-scopes"],
)


async def resolve_scope_or_422(scope):
    try:
        return await asyncio.to_thread(scope_resolver.resolve, scope)
    except ScopeResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/preview", response_model=TargetPreviewResponse)
async def preview_target_scope(request: TargetPreviewRequest) -> TargetPreviewResponse:
    tables = await resolve_scope_or_422(request.scope)
    return TargetPreviewResponse(
        scope=request.scope,
        total_tables=len(tables),
        tables=tables,
    )
