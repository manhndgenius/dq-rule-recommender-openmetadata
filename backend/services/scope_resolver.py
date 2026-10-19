"""Resolve canonical target scopes into a stable table-FQN snapshot."""

from __future__ import annotations

from typing import Iterable, List

from backend.contracts.target_scope import (
    DatabaseTargetScope,
    SchemasTargetScope,
    TablesTargetScope,
    TargetScope,
)
from backend.integrations.openmetadata.client import OpenMetadataClient, openmetadata_client


class ScopeResolutionError(RuntimeError):
    pass


class ScopeResolver:
    def __init__(self, client: OpenMetadataClient = openmetadata_client):
        self.client = client

    @staticmethod
    def _canonical_fqns(entities: Iterable[dict]) -> List[str]:
        seen = set()
        result = []
        for entity in entities:
            fqn = entity.get("fullyQualifiedName") or entity.get("fqn")
            if not fqn or fqn in seen:
                continue
            # Views can still receive DQ rules. Only deleted/malformed entities
            # are excluded here; product-level view filtering can be an option.
            seen.add(fqn)
            result.append(fqn)
        return sorted(result)

    def resolve(self, scope: TargetScope) -> List[str]:
        try:
            if isinstance(scope, TablesTargetScope):
                return sorted({
                    self.client.resolve_table_fqn_strict(table_fqn)
                    for table_fqn in scope.table_fqns
                })

            if isinstance(scope, SchemasTargetScope):
                tables = []
                for schema_fqn in scope.schema_fqns:
                    tables.extend(self.client.list_tables_paginated(schema_fqn))
                return self._require_tables(scope, self._canonical_fqns(tables))

            if not isinstance(scope, DatabaseTargetScope):
                raise ScopeResolutionError(f"Unsupported scope type: {scope.type}")
            schemas = self.client.list_schemas_paginated(scope.database_fqn)
            schema_fqns = self._canonical_fqns(schemas)
            if not schema_fqns:
                raise ScopeResolutionError(
                    f"No schemas found in database: {scope.database_fqn}"
                )
            tables = []
            for schema_fqn in schema_fqns:
                tables.extend(self.client.list_tables_paginated(schema_fqn))
            return self._require_tables(scope, self._canonical_fqns(tables))
        except ScopeResolutionError:
            raise
        except Exception as exc:
            raise ScopeResolutionError(
                f"Could not resolve {scope.type.value} scope: {exc}"
            ) from exc

    @staticmethod
    def _require_tables(scope: TargetScope, tables: List[str]) -> List[str]:
        if not tables:
            raise ScopeResolutionError(
                f"No tables found for {scope.type.value} scope"
            )
        return tables


scope_resolver = ScopeResolver()
