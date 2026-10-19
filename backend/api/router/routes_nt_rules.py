"""Catalog and persisted configuration APIs for NT governance rules."""

from typing import NoReturn

from fastapi import APIRouter, HTTPException, Query

from backend.config.settings import settings
from backend.contracts.nt_rule_config import (
    NTRuleConfigListResponse,
    NTRuleConfigResponse,
    UpdateNTRuleConfigRequest,
)
from backend.engine.nt_rules.config_schema import get_nt_rule_config_schema
from backend.storage.nt_rule_config_repository import (
    InvalidNTRuleConfigError,
    NTRuleConfigConflictError,
    UnknownNTRuleError,
    nt_rule_config_repository,
)


router = APIRouter(
    prefix=f"{settings.api_prefix}/nt-rules",
    tags=["nt-rules"],
)


@router.get("/config-schema")
def get_config_schema():
    """Return versioned field metadata and defaults for all 15 NT rules."""
    return get_nt_rule_config_schema()


def _raise_api_error(exc: Exception) -> NoReturn:
    if isinstance(exc, UnknownNTRuleError):
        raise HTTPException(status_code=404, detail="NT rule not found") from exc
    if isinstance(exc, InvalidNTRuleConfigError):
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Invalid NT rule configuration",
                "errors": exc.errors,
            },
        ) from exc
    if isinstance(exc, NTRuleConfigConflictError):
        raise HTTPException(
            status_code=409,
            detail={
                "message": "NT rule configuration was modified",
                "expected_version": exc.expected_version,
                "current_version": exc.current_version,
            },
        ) from exc
    raise HTTPException(
        status_code=503,
        detail="PostgreSQL NT rule configuration storage is unavailable",
    ) from exc


@router.get("/configs", response_model=NTRuleConfigListResponse)
def list_configs() -> NTRuleConfigListResponse:
    try:
        configs = nt_rule_config_repository.list_all()
    except Exception as exc:
        _raise_api_error(exc)
    return NTRuleConfigListResponse(total=len(configs), data=configs)


@router.get(
    "/{rule_name}/config",
    response_model=NTRuleConfigResponse,
)
def get_rule_config(rule_name: str) -> NTRuleConfigResponse:
    try:
        config = nt_rule_config_repository.get(rule_name)
    except Exception as exc:
        _raise_api_error(exc)
    return NTRuleConfigResponse.model_validate(config)


@router.put(
    "/{rule_name}/config",
    response_model=NTRuleConfigResponse,
)
def update_rule_config(
    rule_name: str,
    request: UpdateNTRuleConfigRequest,
) -> NTRuleConfigResponse:
    try:
        config = nt_rule_config_repository.upsert(
            rule_name=rule_name,
            config=request.config,
            expected_version=request.expected_version,
            enabled=request.enabled,
            updated_by=request.updated_by,
        )
    except Exception as exc:
        _raise_api_error(exc)
    return NTRuleConfigResponse.model_validate(config)


@router.delete(
    "/{rule_name}/config",
    response_model=NTRuleConfigResponse,
)
def delete_rule_config(
    rule_name: str,
    expected_version: int = Query(ge=0),
) -> NTRuleConfigResponse:
    try:
        config = nt_rule_config_repository.delete(
            rule_name,
            expected_version,
        )
    except Exception as exc:
        _raise_api_error(exc)
    return NTRuleConfigResponse.model_validate(config)
