"""Canonical target scopes shared by bulk DQ operations."""

from __future__ import annotations

from enum import Enum
from typing import Annotated, List, Literal, Union

from pydantic import BaseModel, Field, field_validator


class TargetScopeType(str, Enum):
    TABLES = "TABLES"
    SCHEMAS = "SCHEMAS"
    DATABASE = "DATABASE"


def _clean_fqns(values: List[str]) -> List[str]:
    cleaned = [value.strip() for value in values if value and value.strip()]
    return list(dict.fromkeys(cleaned))


class TablesTargetScope(BaseModel):
    type: Literal[TargetScopeType.TABLES] = TargetScopeType.TABLES
    table_fqns: List[str] = Field(min_length=1)

    @field_validator("table_fqns")
    @classmethod
    def validate_table_fqns(cls, values: List[str]) -> List[str]:
        values = _clean_fqns(values)
        if not values:
            raise ValueError("At least one table FQN is required")
        return values


class SchemasTargetScope(BaseModel):
    type: Literal[TargetScopeType.SCHEMAS] = TargetScopeType.SCHEMAS
    schema_fqns: List[str] = Field(min_length=1)

    @field_validator("schema_fqns")
    @classmethod
    def validate_schema_fqns(cls, values: List[str]) -> List[str]:
        values = _clean_fqns(values)
        if not values:
            raise ValueError("At least one schema FQN is required")
        return values


class DatabaseTargetScope(BaseModel):
    type: Literal[TargetScopeType.DATABASE] = TargetScopeType.DATABASE
    database_fqn: str = Field(min_length=1)

    @field_validator("database_fqn")
    @classmethod
    def validate_database_fqn(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Database FQN is required")
        return value


TargetScope = Annotated[
    Union[TablesTargetScope, SchemasTargetScope, DatabaseTargetScope],
    Field(discriminator="type"),
]


class TargetPreviewRequest(BaseModel):
    scope: TargetScope


class TargetPreviewResponse(BaseModel):
    scope: TargetScope
    total_tables: int
    tables: List[str]
