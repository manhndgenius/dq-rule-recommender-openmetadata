"""Strict OpenMetadata input loader for metadata-only NT evaluations."""

from __future__ import annotations

import re
from typing import Any, List, Optional

from backend.contracts.nt_execution import (
    NTColumnMetadata,
    NTExecutionInputs,
    NTMetadataContext,
    NTTestCaseTarget,
    NTTestDefinition,
)
from backend.integrations.openmetadata.client import OpenMetadataClient


class NTMetadataLoader:
    """Build typed NT inputs without datasource or demo fallbacks."""

    def __init__(self, client: OpenMetadataClient):
        self.client = client

    @staticmethod
    def _reference_name(reference: Any) -> Optional[str]:
        if isinstance(reference, dict):
            value = reference.get("name") or reference.get("fullyQualifiedName")
            return str(value) if value else None
        return str(reference) if reference else None

    def load_context(
        self,
        table_fqn: str,
        include_column_profiles: bool = True,
        include_catalog_tables: bool = True,
    ) -> NTMetadataContext:
        raw = self.client.get_table_metadata_for_nt(
            table_fqn,
            include_column_profiles=include_column_profiles,
        )
        columns = [
            NTColumnMetadata(
                name=str(column.get("name") or ""),
                fully_qualified_name=column.get("fullyQualifiedName"),
                data_type=str(column.get("dataType") or "UNKNOWN"),
                data_type_display=column.get("dataTypeDisplay"),
                description=column.get("description"),
                constraint=column.get("constraint"),
                tags=column.get("tags") or [],
                profile=column.get("profile"),
            )
            for column in raw.get("columns") or []
        ]
        database = raw.get("database") or {}
        database_fqn = (
            database.get("fullyQualifiedName")
            if isinstance(database, dict)
            else None
        )
        catalog_tables = raw.get("catalogTables") or []
        if include_catalog_tables and database_fqn and not catalog_tables:
            catalog_tables = self.client.list_database_tables_for_nt(database_fqn)

        return NTMetadataContext(
            table_id=raw.get("id"),
            table_fqn=raw["fullyQualifiedName"],
            table_name=raw.get("name") or raw["fullyQualifiedName"].split(".")[-1],
            table_type=raw.get("tableType"),
            description=raw.get("description"),
            service=raw.get("service"),
            database=database or None,
            database_schema=raw.get("databaseSchema"),
            owners=raw.get("owners") or [],
            domains=raw.get("domains") or [],
            tags=raw.get("tags") or [],
            columns=columns,
            table_constraints=raw.get("tableConstraints") or [],
            catalog_tables=catalog_tables,
            profile=raw.get("profile"),
        )

    def load_definitions(self, prefix: str = "NT") -> List[NTTestDefinition]:
        definitions: List[NTTestDefinition] = []
        for raw in self.client.list_nt_test_definitions(prefix=prefix):
            definition_id = raw.get("id")
            name = raw.get("name")
            if not definition_id or not name:
                raise RuntimeError(
                    "OpenMetadata NT Test Definition is missing id or name"
                )
            definitions.append(
                NTTestDefinition(
                    id=str(definition_id),
                    name=str(name),
                    fully_qualified_name=str(
                        raw.get("fullyQualifiedName") or name
                    ),
                    display_name=raw.get("displayName"),
                    description=raw.get("description"),
                    entity_type=raw.get("entityType"),
                    parameter_definition=raw.get("parameterDefinition") or [],
                    enabled=raw.get("enabled", True),
                    validator_class=raw.get("validatorClass"),
                    sql_expression=raw.get("sqlExpression"),
                    rule_config=raw.get("ruleConfig") or {},
                )
            )
        return definitions

    def load_test_cases(
        self,
        table_fqn: str,
        prefix: str = "NT",
    ) -> List[NTTestCaseTarget]:
        return self._targets(
            self.client.get_table_nt_test_cases(table_fqn, prefix=prefix)
        )

    def load_test_suite_cases(
        self,
        test_suite_fqn: str,
        prefix: str = "NT",
        test_case_names: Optional[List[str]] = None,
    ) -> List[NTTestCaseTarget]:
        raw_cases = self.client.get_test_suite_nt_test_cases(
            test_suite_fqn,
            prefix=prefix,
        )
        selected = set(test_case_names or [])
        if test_case_names is not None:
            raw_cases = [
                case
                for case in raw_cases
                if case.get("name") in selected
                or case.get("fullyQualifiedName") in selected
            ]
        return self._targets(raw_cases)

    def _targets(self, raw_cases: List[dict]) -> List[NTTestCaseTarget]:
        targets: List[NTTestCaseTarget] = []
        for raw in raw_cases:
            test_case_id = raw.get("id")
            name = raw.get("name")
            test_case_fqn = raw.get("fullyQualifiedName")
            if not test_case_id or not name or not test_case_fqn:
                raise RuntimeError(
                    "OpenMetadata NT Test Case is missing id, name, or fullyQualifiedName"
                )
            definition = raw.get("testDefinition") or {}
            entity_link = raw.get("entityLink")
            table_match = re.search(
                r"<#E::table::(.+?)(?:::[^:>]+)?>(?:$|\s)",
                str(entity_link or ""),
            )
            targets.append(
                NTTestCaseTarget(
                    id=str(test_case_id),
                    name=str(name),
                    fully_qualified_name=str(test_case_fqn),
                    test_definition_id=(
                        str(definition.get("id"))
                        if isinstance(definition, dict) and definition.get("id")
                        else None
                    ),
                    test_definition_name=self._reference_name(definition),
                    entity_link=entity_link,
                    table_fqn=table_match.group(1) if table_match else None,
                )
            )
        return targets

    def load_inputs(
        self,
        table_fqn: str,
        include_column_profiles: bool = True,
        include_catalog_tables: bool = True,
        prefix: str = "NT",
    ) -> NTExecutionInputs:
        return NTExecutionInputs(
            metadata=self.load_context(
                table_fqn,
                include_column_profiles=include_column_profiles,
                include_catalog_tables=include_catalog_tables,
            ),
            definitions=self.load_definitions(prefix=prefix),
            test_cases=self.load_test_cases(table_fqn, prefix=prefix),
        )
