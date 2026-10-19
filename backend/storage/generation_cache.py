"""Process-local mirror; PostgreSQL is the durable source of truth."""

from __future__ import annotations

from threading import RLock
from typing import Dict, Iterable, List

from backend.contracts.candidate_rule import CandidateRule


class GenerationCache:
    def __init__(self) -> None:
        self._rules: Dict[str, Dict[str, List[CandidateRule]]] = {}
        self._lock = RLock()

    def save(
        self,
        table_fqn: str,
        engine: str,
        rules: Iterable[CandidateRule],
    ) -> None:
        with self._lock:
            self._rules.setdefault(table_fqn, {})[engine] = [
                rule.model_copy(deep=True) for rule in rules
            ]

    def get(self, table_fqn: str, engine: str | None = None) -> List[CandidateRule]:
        with self._lock:
            by_engine = self._rules.get(table_fqn, {})
            if engine:
                return [rule.model_copy(deep=True) for rule in by_engine.get(engine, [])]
            return [
                rule.model_copy(deep=True)
                for rules in by_engine.values()
                for rule in rules
            ]

    def update_status(
        self,
        rule_id: str,
        status: str,
        edited_parameters: dict | None = None,
    ) -> bool:
        with self._lock:
            for by_engine in self._rules.values():
                for rules in by_engine.values():
                    for rule in rules:
                        if rule.id != rule_id:
                            continue
                        rule.status = status
                        if edited_parameters is not None:
                            rule.edited_parameters = edited_parameters
                        return True
        return False


generation_cache = GenerationCache()
