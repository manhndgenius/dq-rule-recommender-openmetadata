"""Contracts shared by the metadata-only NT governance runner.

These models deliberately contain no datasource connection information.  An
NT execution is evaluated exclusively from metadata returned by OpenMetadata.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class NTOutcome(str, Enum):
    PASS = "PASS"
    WARNING = "WARNING"
    FAIL = "FAIL"
    ERROR = "ERROR"


class NTRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILED = "FAILED"


class NTRunItemStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"
    SKIPPED = "SKIPPED"


class NTColumnMetadata(BaseModel):
    name: str
    fully_qualified_name: Optional[str] = None
    data_type: str = "UNKNOWN"
    data_type_display: Optional[str] = None
    description: Optional[str] = None
    constraint: Optional[str] = None
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    profile: Optional[Dict[str, Any]] = None


class NTMetadataContext(BaseModel):
    """Unmodified governance metadata loaded from OpenMetadata.

    Missing metadata stays missing.  The NT loader must never synthesize a
    description, owner, domain, tag, constraint, or profile value.
    """

    table_id: Optional[str] = None
    table_fqn: str
    table_name: str
    table_type: Optional[str] = None
    description: Optional[str] = None
    service: Optional[Dict[str, Any]] = None
    database: Optional[Dict[str, Any]] = None
    database_schema: Optional[Dict[str, Any]] = None
    owners: List[Dict[str, Any]] = Field(default_factory=list)
    domains: List[Dict[str, Any]] = Field(default_factory=list)
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[NTColumnMetadata] = Field(default_factory=list)
    table_constraints: List[Dict[str, Any]] = Field(default_factory=list)
    catalog_tables: List[Dict[str, Any]] = Field(default_factory=list)
    profile: Optional[Dict[str, Any]] = None
    metadata_source: str = "OPENMETADATA"


class NTTestDefinition(BaseModel):
    id: str
    name: str
    fully_qualified_name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    entity_type: Optional[str] = None
    parameter_definition: List[Dict[str, Any]] = Field(default_factory=list)
    enabled: bool = True
    validator_class: Optional[str] = None
    sql_expression: Optional[str] = None
    rule_config: Dict[str, Any] = Field(default_factory=dict)


class NTTestCaseTarget(BaseModel):
    id: str
    name: str
    fully_qualified_name: str
    test_definition_id: Optional[str] = None
    test_definition_name: Optional[str] = None
    entity_link: Optional[str] = None
    table_fqn: Optional[str] = None


class NTExecutionInputs(BaseModel):
    metadata: NTMetadataContext
    definitions: List[NTTestDefinition] = Field(default_factory=list)
    test_cases: List[NTTestCaseTarget] = Field(default_factory=list)


class CreateNTRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    table_fqn: Optional[str] = Field(default=None, min_length=1)
    test_suite_fqn: Optional[str] = Field(default=None, min_length=1)
    test_case_names: Optional[List[str]] = None
    pipeline_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_scope(self) -> "CreateNTRunRequest":
        if bool(self.table_fqn) == bool(self.test_suite_fqn):
            raise ValueError(
                "Exactly one of table_fqn or test_suite_fqn is required"
            )
        return self


class NTRuleResult(BaseModel):
    definition_name: str
    outcome: NTOutcome
    message: str
    expected: Dict[str, Any] = Field(default_factory=dict)
    observed: Dict[str, Any] = Field(default_factory=dict)
    evidence: Dict[str, Any] = Field(default_factory=dict)
    affected_columns: List[str] = Field(default_factory=list)
    error_code: Optional[str] = None

    @property
    def openmetadata_status(self) -> str:
        return {
            NTOutcome.PASS: "Success",
            NTOutcome.WARNING: "Failed",
            NTOutcome.FAIL: "Failed",
            NTOutcome.ERROR: "Aborted",
        }[self.outcome]

    def test_result_values(self) -> List[Dict[str, str]]:
        values: Dict[str, Any] = {
            "outcome": self.outcome.value,
            "expected": self.expected,
            "observed": self.observed,
            "evidence": self.evidence,
            "affectedColumns": self.affected_columns,
        }
        if self.error_code:
            values["errorCode"] = self.error_code

        def serialize(value: Any) -> str:
            if isinstance(value, str):
                return value
            return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

        return [
            {"name": name, "value": serialize(value)}
            for name, value in values.items()
        ]


class NTRunItem(BaseModel):
    item_id: str = Field(default_factory=lambda: str(uuid4()))
    definition_id: str
    definition_name: str
    test_case_id: Optional[str] = None
    test_case_fqn: Optional[str] = None
    table_fqn: str
    status: NTRunItemStatus = NTRunItemStatus.PENDING
    result: Optional[NTRuleResult] = None
    error: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class NTRun(BaseModel):
    run_id: str = Field(default_factory=lambda: str(uuid4()))
    source_run_id: Optional[str] = None
    table_fqn: Optional[str] = None
    test_suite_fqn: Optional[str] = None
    pipeline_id: Optional[str] = None
    rule_configs: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    status: NTRunStatus = NTRunStatus.PENDING
    items: List[NTRunItem] = Field(default_factory=list)
    created_at: str = Field(default_factory=utc_now)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class NTRunSummary(BaseModel):
    run_id: str
    source_run_id: Optional[str] = None
    table_fqn: Optional[str] = None
    test_suite_fqn: Optional[str] = None
    pipeline_id: Optional[str] = None
    status: NTRunStatus
    total_items: int
    processed_items: int
    completed_items: int
    error_items: int
    skipped_items: int
    outcome_counts: Dict[str, int] = Field(default_factory=dict)
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class RetryNTRunRequest(BaseModel):
    definition_names: Optional[List[str]] = None
    include_skipped: bool = True
