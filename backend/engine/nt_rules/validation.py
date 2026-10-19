"""Server-side validation for NT rule configuration supplied by the UI."""

from __future__ import annotations

import re
from numbers import Real
from typing import Any, Dict, Iterable, List

from backend.engine.nt_rules.config import DEFAULT_RULE_CONFIG


STRING_LIST_FIELDS = {
    "excludedColumns",
    "excludedPatterns",
    "booleanTypes",
    "allowedPrefixes",
    "requiredColumns",
    "requiredFields",
    "expectedTypes",
    "allowedDomains",
    "allowedOwnerTypes",
    "includedColumns",
    "namePatterns",
    "excludedSchemas",
}
BOOLEAN_FIELDS = {"requireAll", "caseSensitive", "allowComposite"}
NON_NEGATIVE_INTEGER_FIELDS = {
    "minimumDescriptionLength",
    "warningThreshold",
    "failureThreshold",
    "minimumOwnerCount",
    "minimumMatches",
}


def _validate_string_list(name: str, value: Any, errors: List[str]) -> None:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        errors.append(f"{name} must be a list of non-empty strings")


def _validate_regex(name: str, pattern: Any, errors: List[str]) -> None:
    if pattern is None:
        return
    if not isinstance(pattern, str):
        errors.append(f"{name} must be a string")
        return
    try:
        re.compile(pattern)
    except re.error as exc:
        errors.append(f"{name} is not a valid regex: {exc}")


def _validate_regex_list(name: str, patterns: Any, errors: List[str]) -> None:
    _validate_string_list(name, patterns, errors)
    if not isinstance(patterns, list):
        return
    for index, pattern in enumerate(patterns):
        if isinstance(pattern, str):
            _validate_regex(f"{name}[{index}]", pattern, errors)


def _validate_number(
    name: str,
    value: Any,
    errors: List[str],
    minimum: float = 0,
    maximum: float | None = None,
    integer: bool = False,
) -> None:
    if isinstance(value, bool) or not isinstance(value, Real):
        errors.append(f"{name} must be a number")
        return
    if integer and not isinstance(value, int):
        errors.append(f"{name} must be an integer")
    if value < minimum:
        errors.append(f"{name} must be greater than or equal to {minimum}")
    if maximum is not None and value > maximum:
        errors.append(f"{name} must be less than or equal to {maximum}")


def _validate_mapping_list(
    name: str,
    value: Any,
    key_field: str,
    errors: List[str],
) -> None:
    if not isinstance(value, list) or not value:
        errors.append(f"{name} must be a non-empty list")
        return
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            errors.append(f"{name}[{index}] must be an object")
            continue
        key = item.get(key_field)
        if not isinstance(key, str) or not key.strip():
            errors.append(f"{name}[{index}].{key_field} is required")
        _validate_string_list(
            f"{name}[{index}].allowedTypes",
            item.get("allowedTypes"),
            errors,
        )


def _safe_string_items(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]


def _duplicates(left: Iterable[str], right: Iterable[str]) -> List[str]:
    return sorted(
        {item.lower() for item in left if isinstance(item, str)}
        & {item.lower() for item in right if isinstance(item, str)}
    )


def validate_nt_rule_config(
    definition_name: str,
    config: Dict[str, Any],
) -> List[str]:
    """Validate an effective config and return all errors without raising."""
    defaults = DEFAULT_RULE_CONFIG.get(definition_name)
    if defaults is None:
        return [f"Unknown NT rule: {definition_name}"]
    if not isinstance(config, dict):
        return ["config must be an object"]

    errors: List[str] = []
    unknown = sorted(set(config) - set(defaults))
    if unknown:
        errors.append(f"Unknown parameters: {', '.join(unknown)}")

    for name in STRING_LIST_FIELDS & set(config):
        _validate_string_list(name, config[name], errors)
    for name in BOOLEAN_FIELDS & set(config):
        if not isinstance(config[name], bool):
            errors.append(f"{name} must be a boolean")

    if "nameRegex" in config:
        _validate_regex("nameRegex", config["nameRegex"], errors)
    if "expectedConstraintNamePattern" in config:
        _validate_regex(
            "expectedConstraintNamePattern",
            config["expectedConstraintNamePattern"],
            errors,
        )
    for name in {"excludedPatterns", "namePatterns"} & set(config):
        _validate_regex_list(name, config[name], errors)

    for name in NON_NEGATIVE_INTEGER_FIELDS & set(config):
        minimum = 1 if name == "minimumMatches" else 0
        is_percentage = definition_name == "NT13_NullableRate" and name in {
            "warningThreshold",
            "failureThreshold",
        }
        _validate_number(
            name,
            config[name],
            errors,
            minimum=minimum,
            maximum=100 if is_percentage else None,
            integer=not is_percentage,
        )

    if definition_name in {"NT11_TableTooWide", "NT13_NullableRate"}:
        warning = config.get("warningThreshold")
        failure = config.get("failureThreshold")
        if (
            isinstance(warning, Real)
            and not isinstance(warning, bool)
            and isinstance(failure, Real)
            and not isinstance(failure, bool)
            and warning > failure
        ):
            errors.append(
                "warningThreshold must be less than or equal to failureThreshold"
            )

    if definition_name == "NT5_DateTimeColumns":
        _validate_mapping_list(
            "suffixTypeMappings",
            config.get("suffixTypeMappings"),
            "suffix",
            errors,
        )
    if definition_name == "NT6_SoftDelete":
        _validate_mapping_list(
            "acceptedStrategies",
            config.get("acceptedStrategies"),
            "column",
            errors,
        )
    if definition_name == "NT7_TableComment":
        invalid = sorted(
            set(_safe_string_items(config.get("requiredFields")))
            - {"description", "domains", "owners", "tags"}
        )
        if invalid:
            errors.append(f"requiredFields contains unsupported values: {', '.join(invalid)}")
    if definition_name == "NT12_DomainOwner":
        invalid = sorted(
            set(_safe_string_items(config.get("requiredFields")))
            - {"domains", "owners"}
        )
        if invalid:
            errors.append(f"requiredFields contains unsupported values: {', '.join(invalid)}")
    if definition_name == "NT13_NullableRate":
        overlap = _duplicates(
            _safe_string_items(config.get("includedColumns")),
            _safe_string_items(config.get("excludedColumns")),
        )
        if overlap:
            errors.append(
                "includedColumns and excludedColumns overlap: " + ", ".join(overlap)
            )
    if definition_name == "NT14_BusinessKey" and config.get(
        "missingOutcome"
    ) != "FAIL":
        errors.append("missingOutcome must be FAIL")
    if definition_name == "NT16_DuplicateTable" and config.get(
        "comparisonScope"
    ) != "DATABASE":
        errors.append("comparisonScope must be DATABASE")
    if "expectedColumn" in config and (
        not isinstance(config["expectedColumn"], str)
        or not config["expectedColumn"].strip()
    ):
        errors.append("expectedColumn must be a non-empty string")

    return errors
