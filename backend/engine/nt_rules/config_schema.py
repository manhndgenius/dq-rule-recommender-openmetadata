"""UI form schema for the 15 configurable metadata-only NT rules."""

from __future__ import annotations

import copy
from typing import Any, Dict, List

from backend.engine.nt_rules.config import DEFAULT_RULE_CONFIG


NT_RULE_DISPLAY_NAMES: Dict[str, str] = {
    "NT1_TableNaming": "Table Naming Convention",
    "NT2_ColumnNaming": "Column Naming Convention",
    "NT3_BooleanNaming": "Boolean Naming",
    "NT4_AuditColumns": "Audit Columns",
    "NT5_DateTimeColumns": "Date Time Columns",
    "NT6_SoftDelete": "Soft Delete",
    "NT7_TableComment": "Table Comment Standard",
    "NT8_PrimaryKeyStandard": "Primary Key Standard",
    "NT9_PrimaryKeyMissing": "Primary Key Missing",
    "NT10_ColumnDescription": "Column Description",
    "NT11_TableTooWide": "Table Too Wide",
    "NT12_DomainOwner": "Domain Owner Validation",
    "NT13_NullableRate": "Nullable Rate",
    "NT14_BusinessKey": "Missing Business Key",
    "NT16_DuplicateTable": "Duplicate Table Detection",
}


NT_RULE_FORM_FIELDS: Dict[str, List[Dict[str, Any]]] = {
    "NT1_TableNaming": [
        {"name": "nameRegex", "label": "Name regex", "control": "REGEX"},
    ],
    "NT2_ColumnNaming": [
        {"name": "nameRegex", "label": "Name regex", "control": "REGEX"},
        {
            "name": "excludedColumns",
            "label": "Excluded columns",
            "control": "TAG_LIST",
        },
        {
            "name": "excludedPatterns",
            "label": "Excluded patterns",
            "control": "REGEX_LIST",
        },
    ],
    "NT3_BooleanNaming": [
        {
            "name": "booleanTypes",
            "label": "Boolean data types",
            "control": "MULTI_SELECT",
            "options": ["BOOLEAN", "BOOL", "BIT"],
            "allowCustom": True,
        },
        {
            "name": "allowedPrefixes",
            "label": "Allowed prefixes",
            "control": "TAG_LIST",
        },
        {
            "name": "excludedColumns",
            "label": "Excluded columns",
            "control": "TAG_LIST",
        },
    ],
    "NT4_AuditColumns": [
        {
            "name": "requiredColumns",
            "label": "Required audit columns",
            "control": "TAG_LIST",
        },
        {"name": "requireAll", "label": "Require all", "control": "BOOLEAN"},
        {
            "name": "caseSensitive",
            "label": "Case sensitive",
            "control": "BOOLEAN",
        },
    ],
    "NT5_DateTimeColumns": [
        {
            "name": "suffixTypeMappings",
            "label": "Suffix and allowed type mappings",
            "control": "EDITABLE_MAPPING",
            "columns": [
                {"name": "suffix", "control": "TEXT"},
                {"name": "allowedTypes", "control": "TAG_LIST"},
            ],
        },
        {
            "name": "excludedColumns",
            "label": "Excluded columns",
            "control": "TAG_LIST",
        },
    ],
    "NT6_SoftDelete": [
        {
            "name": "acceptedStrategies",
            "label": "Accepted soft-delete strategies",
            "control": "EDITABLE_MAPPING",
            "columns": [
                {"name": "column", "control": "TEXT"},
                {"name": "allowedTypes", "control": "TAG_LIST"},
            ],
        },
    ],
    "NT7_TableComment": [
        {
            "name": "requiredFields",
            "label": "Required metadata fields",
            "control": "MULTI_SELECT",
            "options": ["description", "domains", "owners", "tags"],
        },
        {
            "name": "minimumDescriptionLength",
            "label": "Minimum description length",
            "control": "NUMBER",
            "minimum": 0,
            "integer": True,
        },
    ],
    "NT8_PrimaryKeyStandard": [
        {
            "name": "expectedColumn",
            "label": "Expected primary-key column",
            "control": "TEXT",
        },
        {
            "name": "expectedTypes",
            "label": "Expected primary-key data types",
            "control": "MULTI_SELECT",
            "options": ["UUID", "BIGINT", "INT", "INTEGER"],
            "allowCustom": True,
        },
        {
            "name": "allowComposite",
            "label": "Allow composite primary key",
            "control": "BOOLEAN",
        },
        {
            "name": "expectedConstraintNamePattern",
            "label": "Constraint name regex",
            "control": "REGEX",
            "optional": True,
        },
    ],
    "NT9_PrimaryKeyMissing": [],
    "NT10_ColumnDescription": [
        {
            "name": "excludedColumns",
            "label": "Excluded columns",
            "control": "TAG_LIST",
        },
        {
            "name": "excludedPatterns",
            "label": "Excluded patterns",
            "control": "REGEX_LIST",
        },
        {
            "name": "minimumDescriptionLength",
            "label": "Minimum description length",
            "control": "NUMBER",
            "minimum": 0,
            "integer": True,
        },
    ],
    "NT11_TableTooWide": [
        {
            "name": "warningThreshold",
            "label": "Warning threshold",
            "control": "NUMBER",
            "minimum": 0,
            "integer": True,
        },
        {
            "name": "failureThreshold",
            "label": "Failure threshold",
            "control": "NUMBER",
            "minimum": 0,
            "integer": True,
        },
        {
            "name": "excludedColumns",
            "label": "Excluded columns",
            "control": "TAG_LIST",
        },
    ],
    "NT12_DomainOwner": [
        {
            "name": "requiredFields",
            "label": "Required ownership fields",
            "control": "MULTI_SELECT",
            "options": ["domains", "owners"],
        },
        {
            "name": "allowedDomains",
            "label": "Allowed domains",
            "control": "TAG_LIST",
        },
        {
            "name": "minimumOwnerCount",
            "label": "Minimum owner count",
            "control": "NUMBER",
            "minimum": 0,
            "integer": True,
        },
    ],
    "NT13_NullableRate": [
        {
            "name": "warningThreshold",
            "label": "Warning threshold (%)",
            "control": "NUMBER",
            "minimum": 0,
            "maximum": 100,
        },
        {
            "name": "failureThreshold",
            "label": "Failure threshold (%)",
            "control": "NUMBER",
            "minimum": 0,
            "maximum": 100,
        },
        {
            "name": "includedColumns",
            "label": "Included columns",
            "control": "TAG_LIST",
        },
        {
            "name": "excludedColumns",
            "label": "Excluded columns",
            "control": "TAG_LIST",
        },
    ],
    "NT14_BusinessKey": [
        {
            "name": "namePatterns",
            "label": "Business-key name patterns",
            "control": "REGEX_LIST",
        },
        {
            "name": "minimumMatches",
            "label": "Minimum matches",
            "control": "NUMBER",
            "minimum": 1,
            "integer": True,
        },
        {
            "name": "excludedColumns",
            "label": "Excluded columns",
            "control": "TAG_LIST",
        },
        {
            "name": "missingOutcome",
            "label": "Outcome when missing",
            "control": "SELECT",
            "options": ["WARNING", "FAIL"],
        },
    ],
    "NT16_DuplicateTable": [
        {
            "name": "comparisonScope",
            "label": "Comparison scope",
            "control": "SELECT",
            "options": ["DATABASE"],
            "disabled": True,
        },
        {
            "name": "caseSensitive",
            "label": "Case sensitive",
            "control": "BOOLEAN",
        },
        {
            "name": "excludedSchemas",
            "label": "Excluded schemas",
            "control": "TAG_LIST",
        },
    ],
}


def get_nt_rule_config_schema() -> Dict[str, Any]:
    """Return a serializable, versioned catalog consumed by the OM UI."""
    return {
        "version": 1,
        "rules": [
            {
                "name": name,
                "display_name": NT_RULE_DISPLAY_NAMES[name],
                "configurable": bool(NT_RULE_FORM_FIELDS[name]),
                "fields": copy.deepcopy(NT_RULE_FORM_FIELDS[name]),
                "defaults": copy.deepcopy(defaults),
            }
            for name, defaults in DEFAULT_RULE_CONFIG.items()
        ],
    }
