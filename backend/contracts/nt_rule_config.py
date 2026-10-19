"""Contracts for persisted NT governance rule configuration."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class UpdateNTRuleConfigRequest(BaseModel):
    config: Dict[str, Any]
    expected_version: int = Field(ge=0)
    enabled: bool = True
    updated_by: Optional[str] = Field(default=None, max_length=255)


class NTRuleConfigResponse(BaseModel):
    rule_name: str
    config: Dict[str, Any]
    override: Dict[str, Any]
    enabled: bool
    version: int
    persisted: bool
    updated_by: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class NTRuleConfigListResponse(BaseModel):
    total: int
    data: list[NTRuleConfigResponse]

