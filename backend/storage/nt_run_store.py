"""Thread-safe in-memory storage for NT metadata rule runs."""

from __future__ import annotations

import copy
from threading import RLock
from typing import Dict, Iterable, List, Optional

from backend.contracts.nt_execution import (
    CreateNTRunRequest,
    NTRuleResult,
    NTRun,
    NTRunItem,
    NTRunItemStatus,
    NTRunStatus,
    NTRunSummary,
    NTTestCaseTarget,
    NTTestDefinition,
    utc_now,
)


TERMINAL_ITEM_STATUSES = {
    NTRunItemStatus.COMPLETED,
    NTRunItemStatus.ERROR,
    NTRunItemStatus.SKIPPED,
}


class NTRunStore:
    def __init__(self) -> None:
        self._runs: Dict[str, NTRun] = {}
        self._lock = RLock()

    def create(
        self,
        request: CreateNTRunRequest,
        definitions: Iterable[NTTestDefinition],
        test_cases: Iterable[NTTestCaseTarget],
        source_run_id: Optional[str] = None,
        rule_configs: Optional[Dict[str, Dict]] = None,
    ) -> NTRun:
        definitions_by_id = {definition.id: definition for definition in definitions}
        definitions_by_name = {
            definition.name: definition for definition in definitions
        }
        definitions_by_name.update(
            {definition.fully_qualified_name: definition for definition in definitions}
        )
        items: List[NTRunItem] = []
        for target in test_cases:
            definition = definitions_by_id.get(target.test_definition_id or "")
            definition = definition or definitions_by_name.get(
                target.test_definition_name or ""
            )
            if not definition or not target.table_fqn:
                continue
            items.append(
                NTRunItem(
                    definition_id=definition.id,
                    definition_name=definition.name,
                    test_case_id=target.id,
                    test_case_fqn=target.fully_qualified_name,
                    table_fqn=target.table_fqn,
                )
            )
        run = NTRun(
            source_run_id=source_run_id,
            table_fqn=request.table_fqn,
            test_suite_fqn=request.test_suite_fqn,
            pipeline_id=request.pipeline_id,
            # The runner may execute after the HTTP request has completed.
            # Keep an immutable snapshot of the database configuration.
            rule_configs=copy.deepcopy(rule_configs or {}),
            items=items,
        )
        with self._lock:
            self._runs[run.run_id] = run
        return run.model_copy(deep=True)

    def get(self, run_id: str) -> Optional[NTRun]:
        with self._lock:
            run = self._runs.get(run_id)
            return run.model_copy(deep=True) if run else None

    def start_run(self, run_id: str) -> None:
        with self._lock:
            run = self._runs[run_id]
            run.status = NTRunStatus.RUNNING
            run.started_at = run.started_at or utc_now()

    def start_item(self, run_id: str, item_id: str) -> None:
        with self._lock:
            item = self._item(run_id, item_id)
            item.status = NTRunItemStatus.RUNNING
            item.started_at = utc_now()
            item.finished_at = None
            item.result = None
            item.error = None

    def finish_item(
        self,
        run_id: str,
        item_id: str,
        status: NTRunItemStatus,
        result: Optional[NTRuleResult] = None,
        error: Optional[str] = None,
    ) -> None:
        if status not in TERMINAL_ITEM_STATUSES:
            raise ValueError(f"Item cannot finish with status {status}")
        with self._lock:
            item = self._item(run_id, item_id)
            item.status = status
            item.result = result
            item.error = error
            item.finished_at = utc_now()

    def finish_run(self, run_id: str) -> None:
        with self._lock:
            run = self._runs[run_id]
            completed = sum(
                item.status == NTRunItemStatus.COMPLETED for item in run.items
            )
            unfinished = sum(
                item.status not in TERMINAL_ITEM_STATUSES for item in run.items
            )
            failures = sum(
                item.status in {NTRunItemStatus.ERROR, NTRunItemStatus.SKIPPED}
                for item in run.items
            )
            if completed == len(run.items):
                run.status = NTRunStatus.SUCCESS
            elif completed and (failures or unfinished):
                run.status = NTRunStatus.PARTIAL
            else:
                run.status = NTRunStatus.FAILED
            run.finished_at = utc_now()

    def summary(self, run_id: str) -> Optional[NTRunSummary]:
        run = self.get(run_id)
        if not run:
            return None
        outcome_counts: Dict[str, int] = {}
        for item in run.items:
            if item.result:
                outcome = item.result.outcome.value
                outcome_counts[outcome] = outcome_counts.get(outcome, 0) + 1
        return NTRunSummary(
            run_id=run.run_id,
            source_run_id=run.source_run_id,
            table_fqn=run.table_fqn,
            test_suite_fqn=run.test_suite_fqn,
            pipeline_id=run.pipeline_id,
            status=run.status,
            total_items=len(run.items),
            processed_items=sum(
                item.status in TERMINAL_ITEM_STATUSES for item in run.items
            ),
            completed_items=sum(
                item.status == NTRunItemStatus.COMPLETED for item in run.items
            ),
            error_items=sum(
                item.status == NTRunItemStatus.ERROR for item in run.items
            ),
            skipped_items=sum(
                item.status == NTRunItemStatus.SKIPPED for item in run.items
            ),
            outcome_counts=outcome_counts,
            created_at=run.created_at,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )

    def items(
        self,
        run_id: str,
        status: Optional[NTRunItemStatus] = None,
        definition_name: Optional[str] = None,
    ) -> List[NTRunItem]:
        run = self.get(run_id)
        if not run:
            return []
        return [
            item
            for item in run.items
            if (status is None or item.status == status)
            and (
                definition_name is None
                or item.definition_name == definition_name
            )
        ]

    def _item(self, run_id: str, item_id: str) -> NTRunItem:
        run = self._runs[run_id]
        for item in run.items:
            if item.item_id == item_id:
                return item
        raise KeyError(f"NT run item not found: {item_id}")


nt_run_store = NTRunStore()
