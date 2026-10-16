"""Prepare and execute metadata-only NT rule runs."""

from __future__ import annotations

import logging
from typing import Iterable, Optional

from backend.contracts.nt_execution import (
    CreateNTRunRequest,
    NTRun,
    NTRunItemStatus,
    RetryNTRunRequest,
)
from backend.engine.nt_rules.registry import evaluate_nt_rule
from backend.integrations.openmetadata.client import (
    OpenMetadataClient,
    openmetadata_client,
)
from backend.services.nt_metadata_loader import NTMetadataLoader
from backend.services.nt_test_case_mapper import NTTestCaseMapper
from backend.storage.nt_run_store import NTRunStore, nt_run_store

logger = logging.getLogger("nt_run_service")


class NTRunService:
    def __init__(
        self,
        client: OpenMetadataClient,
        store: NTRunStore,
        loader: Optional[NTMetadataLoader] = None,
        mapper: Optional[NTTestCaseMapper] = None,
    ) -> None:
        self.client = client
        self.store = store
        self.loader = loader or NTMetadataLoader(client)
        self.mapper = mapper or NTTestCaseMapper()

    def prepare(
        self,
        request: CreateNTRunRequest,
        source_run_id: Optional[str] = None,
        definition_names: Optional[Iterable[str]] = None,
    ) -> NTRun:
        selected = set(definition_names or [])
        definitions = [
            definition
            for definition in self.loader.load_definitions()
            if definition.enabled
            and (not selected or definition.name in selected)
        ]
        if selected:
            missing = selected - {definition.name for definition in definitions}
            if missing:
                raise ValueError(
                    "NT Test Definitions not found or disabled: "
                    + ", ".join(sorted(missing))
                )
        if not definitions:
            raise ValueError("No enabled NT Test Definitions were found")

        test_cases = self.loader.load_test_cases(request.table_fqn)
        mapping = self.mapper.map(definitions, test_cases)
        return self.store.create(
            request=request,
            definitions=definitions,
            mapping=mapping,
            source_run_id=source_run_id,
        )

    def run(self, run_id: str) -> None:
        run = self.store.get(run_id)
        if not run:
            raise KeyError(f"NT run not found: {run_id}")
        self.store.start_run(run_id)
        try:
            context = self.loader.load_context(
                run.table_fqn,
                include_column_profiles=True,
                include_catalog_tables=True,
            )
            definitions = {
                definition.name: definition
                for definition in self.loader.load_definitions()
                if definition.enabled
            }
        except Exception as exc:
            logger.exception("Cannot load metadata for NT run %s", run_id)
            self._fail_pending_items(run_id, f"Metadata load failed: {exc}")
            self.store.finish_run(run_id)
            return

        for item in self.store.get(run_id).items:
            self.store.start_item(run_id, item.item_id)
            if not item.test_case_fqn:
                self.store.finish_item(
                    run_id,
                    item.item_id,
                    NTRunItemStatus.SKIPPED,
                    error=(
                        "No existing Test Case is mapped to NT Test Definition "
                        f"{item.definition_name}"
                    ),
                )
                continue
            definition = definitions.get(item.definition_name)
            if not definition:
                self.store.finish_item(
                    run_id,
                    item.item_id,
                    NTRunItemStatus.ERROR,
                    error=f"NT Test Definition is missing: {item.definition_name}",
                )
                continue
            try:
                result = evaluate_nt_rule(definition, context)
                self.client.add_test_case_result(item.test_case_fqn, result)
                self.store.finish_item(
                    run_id,
                    item.item_id,
                    NTRunItemStatus.COMPLETED,
                    result=result,
                )
            except Exception as exc:
                logger.exception(
                    "NT rule %s failed in run %s", item.definition_name, run_id
                )
                self.store.finish_item(
                    run_id,
                    item.item_id,
                    NTRunItemStatus.ERROR,
                    error=str(exc),
                )
        self.store.finish_run(run_id)

    def retry(self, source_run_id: str, request: RetryNTRunRequest) -> NTRun:
        source = self.store.get(source_run_id)
        if not source:
            raise KeyError(f"NT run not found: {source_run_id}")
        allowed = set(request.definition_names or [])
        definition_names = [
            item.definition_name
            for item in source.items
            if (
                item.status == NTRunItemStatus.ERROR
                or (
                    request.include_skipped
                    and item.status == NTRunItemStatus.SKIPPED
                )
            )
            and (not allowed or item.definition_name in allowed)
        ]
        if not definition_names:
            raise ValueError("No failed NT run items matched retry filters")
        return self.prepare(
            CreateNTRunRequest(
                table_fqn=source.table_fqn,
                pipeline_id=source.pipeline_id,
            ),
            source_run_id=source_run_id,
            definition_names=definition_names,
        )

    def _fail_pending_items(self, run_id: str, error: str) -> None:
        run = self.store.get(run_id)
        if not run:
            return
        for item in run.items:
            if item.status == NTRunItemStatus.PENDING:
                self.store.start_item(run_id, item.item_id)
                self.store.finish_item(
                    run_id,
                    item.item_id,
                    NTRunItemStatus.ERROR,
                    error=error,
                )


nt_run_service = NTRunService(openmetadata_client, nt_run_store)
