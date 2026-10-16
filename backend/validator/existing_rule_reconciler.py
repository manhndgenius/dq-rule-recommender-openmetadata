"""Reconcile generated BASIC candidates with Test Cases already in OpenMetadata."""

import hashlib
import json
import re
from typing import Any, Dict, Iterable, List, Tuple

from backend.contracts.candidate_rule import CandidateRule


BASIC_TEST_DEFINITIONS = {
    "columnValuesToBeNotNull",
    "columnValuesToBeUnique",
    "columnValuesToBeBetween",
    "columnValuesToBeInSet",
    "columnValueLengthsToBeBetween",
    "columnValuesToMatchRegex",
    "tableRowCountToBeBetween",
}

STATISTICAL_TEST_DEFINITIONS = {
    "columnValueMeanToBeBetween",
    "columnValueMedianToBeBetween",
    "columnValueStdDevToBeBetween",
    "columnValueMinToBeBetween",
    "columnValueMaxToBeBetween",
}

RULE_TYPE_ALIASES = {
    "columnValuesLengthToBeBetween": "columnValueLengthsToBeBetween",
}


def _canonical_rule_type(rule_type: str) -> str:
    return RULE_TYPE_ALIASES.get(rule_type, rule_type)


def _test_definition_name(test_case: Dict[str, Any]) -> str:
    definition = test_case.get("testDefinition")
    if isinstance(definition, dict):
        return definition.get("name") or definition.get("fullyQualifiedName", "")
    return str(definition or "")


def _target_columns(entity_link: str) -> List[str]:
    match = re.search(r"::columns::([^>]+)>", entity_link or "")
    return [match.group(1)] if match else []


def _parameter_value(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def _parameters(test_case: Dict[str, Any]) -> Dict[str, Any]:
    return {
        item["name"]: _parameter_value(item.get("value"))
        for item in test_case.get("parameterValues") or []
        if item.get("name")
    }


def _identity(rule_type: str, target_columns: Iterable[str]) -> Tuple[str, Tuple[str, ...]]:
    return _canonical_rule_type(rule_type), tuple(sorted(target_columns))


def existing_basic_rules(test_cases: Iterable[Dict[str, Any]]) -> List[CandidateRule]:
    """Convert existing native BASIC Test Cases into read-only APPLIED rules."""
    existing_by_identity: Dict[Tuple[str, Tuple[str, ...]], CandidateRule] = {}

    for test_case in test_cases:
        rule_type = _canonical_rule_type(_test_definition_name(test_case))
        if rule_type not in BASIC_TEST_DEFINITIONS:
            continue

        target_columns = _target_columns(test_case.get("entityLink", ""))
        identity = _identity(rule_type, target_columns)
        if identity in existing_by_identity:
            continue

        test_case_id = str(test_case.get("id") or "")
        stable_source = test_case_id or str(test_case.get("fullyQualifiedName") or identity)
        stable_id = hashlib.md5(stable_source.encode()).hexdigest()[:12]
        existing_by_identity[identity] = CandidateRule(
            id=f"applied_{stable_id}",
            rule_type=rule_type,
            description=test_case.get("displayName") or test_case.get("name"),
            target_columns=target_columns,
            parameters=_parameters(test_case),
            engine="BASIC",
            confidence=1.0,
            reason="This rule already exists as a Test Case in OpenMetadata.",
            evidence={
                "test_case_id": test_case.get("id"),
                "test_case_name": test_case.get("name"),
                "test_case_fqn": test_case.get("fullyQualifiedName"),
            },
            status="APPLIED",
        )

    return list(existing_by_identity.values())


def reconcile_basic_rules(
    generated: Iterable[CandidateRule],
    test_cases: Iterable[Dict[str, Any]],
) -> Tuple[List[CandidateRule], List[CandidateRule], int]:
    """Return displayed rules, new reviewable rules, and duplicate count."""
    generated_rules = list(generated)
    applied_rules = existing_basic_rules(test_cases)
    applied_keys = {
        _identity(rule.rule_type, rule.target_columns) for rule in applied_rules
    }
    new_rules = [
        rule
        for rule in generated_rules
        if _identity(rule.rule_type, rule.target_columns) not in applied_keys
    ]
    duplicate_count = len(generated_rules) - len(new_rules)

    return [*applied_rules, *new_rules], new_rules, duplicate_count


def reconcile_generated_rules(
    generated: Iterable[CandidateRule],
    test_cases: Iterable[Dict[str, Any]],
    engine: str,
) -> Tuple[List[CandidateRule], List[CandidateRule], int]:
    """Reconcile normalized candidates for every engine.

    BASIC keeps the legacy behaviour of also displaying native applied rules.
    Statistical rules use the same native definition/column identity. Advanced
    rules match only custom SQL that is semantically identical after whitespace
    normalization, so unrelated governance SQL is never pulled into the list.
    """
    if engine == "BASIC":
        return reconcile_basic_rules(generated, test_cases)

    generated_rules = list(generated)
    cases = list(test_cases)

    if engine == "STATISTICAL":
        existing_keys = {
            _identity(_test_definition_name(case), _target_columns(case.get("entityLink", "")))
            for case in cases
            if _canonical_rule_type(_test_definition_name(case))
            in STATISTICAL_TEST_DEFINITIONS
        }
        reviewable = []
        displayed = []
        for rule in generated_rules:
            if _identity(rule.rule_type, rule.target_columns) in existing_keys:
                applied = rule.model_copy(deep=True)
                applied.status = "APPLIED"
                displayed.append(applied)
            else:
                displayed.append(rule)
                reviewable.append(rule)
        return displayed, reviewable, len(generated_rules) - len(reviewable)

    if engine == "ADVANCED":
        from backend.storage.rule_identity import normalize_sql

        existing_sql = set()
        for case in cases:
            if _test_definition_name(case) != "tableCustomSQLQuery":
                continue
            params = _parameters(case)
            sql = (
                params.get("sqlExpression")
                or params.get("sql")
                or params.get("query")
            )
            if sql:
                existing_sql.add(normalize_sql(str(sql)))

        reviewable = []
        displayed = []
        for rule in generated_rules:
            candidate_sql = normalize_sql(rule.rendered_sql or rule.sql)
            if candidate_sql and candidate_sql in existing_sql:
                applied = rule.model_copy(deep=True)
                applied.status = "APPLIED"
                displayed.append(applied)
            else:
                displayed.append(rule)
                reviewable.append(rule)
        return displayed, reviewable, len(generated_rules) - len(reviewable)

    return generated_rules, generated_rules, 0
