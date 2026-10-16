"""Resolve TABLE/SCHEMA/DATABASE scopes into canonical table FQNs."""

from __future__ import annotations

from typing import Iterable, List

from backend.contracts.generation_job import GenerationScope, ScopeType
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

    def resolve(self, scope: GenerationScope) -> List[str]:
        target = scope.target_fqn.strip()
        try:
            if scope.type == ScopeType.TABLE:
                return [self.client.resolve_table_fqn_strict(target)]

            if scope.type == ScopeType.SCHEMA:
                tables = self.client.list_tables_paginated(target)
                return self._require_tables(scope, self._canonical_fqns(tables))

            schemas = self.client.list_schemas_paginated(target)
            schema_fqns = self._canonical_fqns(schemas)
            if not schema_fqns:
                raise ScopeResolutionError(f"No schemas found in database: {target}")
            tables = []
            for schema_fqn in schema_fqns:
                tables.extend(self.client.list_tables_paginated(schema_fqn))
            return self._require_tables(scope, self._canonical_fqns(tables))
        except ScopeResolutionError:
            raise
        except Exception as exc:
            raise ScopeResolutionError(
                f"Could not resolve {scope.type.value} scope {target}: {exc}"
            ) from exc

    @staticmethod
    def _require_tables(scope: GenerationScope, tables: List[str]) -> List[str]:
        if not tables:
            raise ScopeResolutionError(
                f"No tables found for {scope.type.value} scope: {scope.target_fqn}"
            )
        return tables


scope_resolver = ScopeResolver()
