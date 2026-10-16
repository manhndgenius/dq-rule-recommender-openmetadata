"""Map NT Test Definitions to the existing Test Cases on a table."""

from __future__ import annotations

import re
from typing import Dict, Iterable, Optional

from backend.contracts.nt_execution import NTTestCaseTarget, NTTestDefinition


LEGACY_NT_CASE_PATTERN = re.compile(
    r"^dq_default_(NT[A-Za-z0-9_]+)_[0-9a-f]{8}$"
)


class NTTestCaseMapper:
    """Prefer native definition references, then deterministic legacy names."""

    @staticmethod
    def legacy_definition_name(test_case: NTTestCaseTarget) -> Optional[str]:
        match = LEGACY_NT_CASE_PATTERN.fullmatch(test_case.name)
        return match.group(1) if match else None

    def map(
        self,
        definitions: Iterable[NTTestDefinition],
        test_cases: Iterable[NTTestCaseTarget],
    ) -> Dict[str, NTTestCaseTarget]:
        definitions = list(definitions)
        test_cases = list(test_cases)
        mapped: Dict[str, NTTestCaseTarget] = {}

        # Native Test Cases carry the actual NT Test Definition reference and
        # always win over an older tableCustomSQLQuery compatibility case.
        for definition in definitions:
            native = next(
                (
                    test_case
                    for test_case in test_cases
                    if test_case.test_definition_id == definition.id
                    or test_case.test_definition_name
                    in {definition.name, definition.fully_qualified_name}
                ),
                None,
            )
            if native:
                mapped[definition.name] = native

        for definition in definitions:
            if definition.name in mapped:
                continue
            legacy = next(
                (
                    test_case
                    for test_case in test_cases
                    if self.legacy_definition_name(test_case) == definition.name
                ),
                None,
            )
            if legacy:
                mapped[definition.name] = legacy
        return mapped
