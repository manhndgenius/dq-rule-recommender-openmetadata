"""Default NT rule configuration and Test Definition config resolution."""

from __future__ import annotations

import copy
import json
from typing import Any, Dict

from backend.contracts.nt_execution import NTTestDefinition


DEFAULT_RULE_CONFIG: Dict[str, Dict[str, Any]] = {
    "NT1_TableNaming": {
        "nameRegex": r"^[a-z][a-z0-9_]*$",
    },
    "NT2_ColumnNaming": {
        "nameRegex": r"^[a-z][a-z0-9_]*$",
        "excludedColumns": [],
        "excludedPatterns": [],
    },
    "NT3_BooleanNaming": {
        "booleanTypes": ["BOOLEAN", "BOOL"],
        "allowedPrefixes": ["is_", "has_", "can_"],
        "excludedColumns": [],
    },
    "NT4_AuditColumns": {
        "requiredColumns": [
            "id",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "is_active",
        ],
        "requireAll": True,
        "caseSensitive": False,
    },
    "NT5_DateTimeColumns": {
        "suffixTypeMappings": [
            {"suffix": "_at", "allowedTypes": ["TIMESTAMPTZ"]},
            {"suffix": "_date", "allowedTypes": ["DATE"]},
        ],
        "excludedColumns": [],
    },
    "NT6_SoftDelete": {
        "acceptedStrategies": [
            {"column": "is_active", "allowedTypes": ["BOOLEAN", "BOOL"]},
            {"column": "deleted_at", "allowedTypes": ["TIMESTAMPTZ"]},
        ],
    },
    "NT7_TableComment": {
        "requiredFields": ["description", "domains", "owners"],
        "minimumDescriptionLength": 1,
    },
    "NT8_PrimaryKeyStandard": {
        "expectedColumn": "id",
        "expectedTypes": ["UUID"],
        "allowComposite": False,
        "expectedConstraintNamePattern": None,
    },
    "NT9_PrimaryKeyMissing": {},
    "NT10_ColumnDescription": {
        "excludedColumns": [
            "id",
            "created_at",
            "created_by",
            "updated_at",
            "updated_by",
            "is_active",
        ],
        "excludedPatterns": [],
        "minimumDescriptionLength": 1,
    },
    "NT11_TableTooWide": {
        "warningThreshold": 50,
        "failureThreshold": 80,
        "excludedColumns": [],
    },
    "NT12_DomainOwner": {
        "requiredFields": ["domains", "owners"],
        "allowedDomains": [
            "Bệnh nhân & Định danh",
            "Hành trình Bệnh nhân",
            "Trải nghiệm & Chăm sóc liên tục",
            "Danh mục Dịch vụ Y tế",
            "Lâm sàng",
            "Tài chính & Doanh thu",
            "Vận hành & Năng lực",
            "Nhân sự Y tế",
            "Quản trị Rủi ro",
            "Tham chiếu & Nền tảng",
        ],
        "minimumOwnerCount": 1,
    },
    "NT13_NullableRate": {
        "warningThreshold": 50.0,
        "failureThreshold": 80.0,
        "excludedColumns": [],
        "includedColumns": [],
    },
    "NT14_BusinessKey": {
        "namePatterns": [r"_code$", r"_no$", r"_number$", r"_ref$"],
        "minimumMatches": 1,
        "excludedColumns": [],
        "missingOutcome": "WARNING",
    },
    "NT16_DuplicateTable": {
        "comparisonScope": "DATABASE",
        "caseSensitive": False,
        "excludedSchemas": [],
    },
}


class NTRuleConfigResolver:
    """Resolve effective configuration without reading Test Case parameters."""

    @staticmethod
    def _parse_value(value: Any) -> Any:
        if not isinstance(value, str):
            return value
        stripped = value.strip()
        if not stripped:
            return value
        try:
            return json.loads(stripped)
        except (TypeError, ValueError):
            return value

    def resolve(self, definition: NTTestDefinition) -> Dict[str, Any]:
        config = copy.deepcopy(DEFAULT_RULE_CONFIG.get(definition.name, {}))

        # ``rule_config`` is the future definition-level configuration edited
        # by the OpenMetadata UI.  It intentionally does not consult Test Case
        # parameterValues.
        config.update(copy.deepcopy(definition.rule_config))

        # Accept definition parameters carrying a default/current value so the
        # evaluator contract remains compatible with a future OM schema/UI.
        for parameter in definition.parameter_definition:
            name = parameter.get("name")
            if not name:
                continue
            if "value" in parameter:
                config[name] = self._parse_value(parameter["value"])
            elif "defaultValue" in parameter:
                config[name] = self._parse_value(parameter["defaultValue"])
        return config
