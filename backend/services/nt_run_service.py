"""Prepare and execute metadata-only NT rule runs."""

from __future__ import annotations

import copy
import logging
from typing import Iterable, Optional

from backend.contracts.nt_execution import (
    CreateNTRunRequest,
    NTOutcome,
    NTRuleResult,
    NTRun,
    NTRunItemStatus,
    RetryNTRunRequest,
)
from backend.engine.nt_rules.config import DEFAULT_RULE_CONFIG
from backend.engine.nt_rules.registry import evaluate_nt_rule
from backend.engine.nt_rules.validation import validate_nt_rule_config
from backend.integrations.openmetadata.client import (
    OpenMetadataClient,
    openmetadata_client,
)
from backend.services.nt_metadata_loader import NTMetadataLoader
from backend.storage.nt_rule_config_repository import (
    NTRuleConfigRepository,
    nt_rule_config_repository,
)
from backend.storage.nt_run_store import NTRunStore, nt_run_store

logger = logging.getLogger("nt_run_service")


class NTRunConfigLoadError(RuntimeError):
    """Raised when a run cannot snapshot persisted NT configuration."""


class NTRunService:
    def __init__(
        self,
        client: OpenMetadataClient,
        store: NTRunStore,
        loader: Optional[NTMetadataLoader] = None,
        mapper: Optional[object] = None,
        config_repository: NTRuleConfigRepository = nt_rule_config_repository,
    ) -> None:
        self.client = client
        self.store = store
        self.loader = loader or NTMetadataLoader(client)
        # Kept as an optional constructor argument for callers created before
        # native NT Test Case relationships became the source of truth.
        self.mapper = mapper
        self.config_repository = config_repository

    def prepare(
        self,
        request: CreateNTRunRequest,
        source_run_id: Optional[str] = None,
        definition_names: Optional[Iterable[str]] = None,
        config_snapshot: Optional[dict[str, dict]] = None,
    ) -> NTRun:
        selected = set(definition_names or [])
        if config_snapshot is None:
            try:
                config_rows = self.config_repository.list_all()
            except Exception as exc:
                raise NTRunConfigLoadError(
                    "Cannot load NT rule configuration from PostgreSQL"
                ) from exc
            effective_configs = {
                row["rule_name"]: copy.deepcopy(row["config"])
                for row in config_rows
                if row["enabled"]
            }
        else:
            effective_configs = copy.deepcopy(config_snapshot)

        enabled_definitions = [
            definition
            for definition in self.loader.load_definitions()
            if definition.enabled and definition.name in effective_configs
        ]
        definitions = [
            definition
            for definition in enabled_definitions
            if not selected or definition.name in selected
        ]
        if selected:
            missing = selected - {definition.name for definition in definitions}
            if missing:
                raise ValueError(
                    "NT Test Definitions not found or disabled: "
                    + ", ".join(sorted(missing))
                )
        if request.table_fqn:
            test_cases = self.loader.load_test_cases(request.table_fqn)
            selected_cases = set(request.test_case_names or [])
            if request.test_case_names is not None:
                test_cases = [
                    test_case
                    for test_case in test_cases
                    if test_case.name in selected_cases
                    or test_case.fully_qualified_name in selected_cases
                ]
            for test_case in test_cases:
                test_case.table_fqn = test_case.table_fqn or request.table_fqn
        else:
            test_cases = self.loader.load_test_suite_cases(
                request.test_suite_fqn,
                test_case_names=request.test_case_names,
            )

        definition_ids = {case.test_definition_id for case in test_cases}
        definition_names = {case.test_definition_name for case in test_cases}
        applied_definitions = [
            definition
            for definition in definitions
            if definition.id in definition_ids
            or definition.name in definition_names
            or definition.fully_qualified_name in definition_names
        ]
        run_configs = {
            definition.name: copy.deepcopy(effective_configs[definition.name])
            for definition in applied_definitions
        }
        return self.store.create(
            request=request,
            definitions=applied_definitions,
            test_cases=test_cases,
            source_run_id=source_run_id,
            rule_configs=run_configs,
        )

    def run(self, run_id: str) -> None:
        run = self.store.get(run_id)
        if not run:
            raise KeyError(f"NT run not found: {run_id}")
        self.store.start_run(run_id)
        try:
            definitions = {
                definition.name: definition
                for definition in self.loader.load_definitions()
                if definition.enabled
            }
        except Exception as exc:
            logger.exception("Cannot load NT definitions for run %s", run_id)
            self._fail_pending_items(run_id, f"Definition load failed: {exc}")
            self.store.finish_run(run_id)
            return

        contexts = {}
        for item in self.store.get(run_id).items:
            self.store.start_item(run_id, item.item_id)
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
                if item.table_fqn not in contexts:
                    contexts[item.table_fqn] = self.loader.load_context(
                        item.table_fqn,
                        include_column_profiles=True,
                        include_catalog_tables=True,
                    )
                context = contexts[item.table_fqn]
                config = copy.deepcopy(
                    DEFAULT_RULE_CONFIG.get(item.definition_name, {})
                )
                config.update(
                    copy.deepcopy(
                        run.rule_configs.get(item.definition_name, {})
                    )
                )
                validation_errors = validate_nt_rule_config(
                    item.definition_name,
                    config,
                )
                if validation_errors:
                    result = NTRuleResult(
                        definition_name=item.definition_name,
                        outcome=NTOutcome.ERROR,
                        message="Cấu hình rule không hợp lệ: "
                        + "; ".join(validation_errors),
                        expected={
                            "allowedParameters": list(
                                DEFAULT_RULE_CONFIG.get(
                                    item.definition_name, {}
                                )
                            )
                        },
                        observed={"ruleConfig": config},
                        evidence={
                            "validationErrors": validation_errors,
                        },
                        error_code="INVALID_RULE_CONFIG",
                    )
                else:
                    result = evaluate_nt_rule(
                        definition,
                        context,
                        config=config,
                    )
                self.client.add_test_case_result(item.test_case_fqn, result)
                self.store.finish_item(
                    run_id,
                    item.item_id,
                    (
                        NTRunItemStatus.ERROR
                        if result.outcome == NTOutcome.ERROR
                        else NTRunItemStatus.COMPLETED
                    ),
                    result=result,
                    error=(
                        result.message
                        if result.outcome == NTOutcome.ERROR
                        else None
                    ),
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
                test_suite_fqn=source.test_suite_fqn,
                pipeline_id=source.pipeline_id,
            ),
            source_run_id=source_run_id,
            definition_names=definition_names,
            config_snapshot=source.rule_configs,
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
