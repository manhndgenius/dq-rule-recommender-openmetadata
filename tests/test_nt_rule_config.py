import copy

import pytest
from fastapi.testclient import TestClient

from backend.engine.nt_rules.config import DEFAULT_RULE_CONFIG
from backend.engine.nt_rules.config_schema import get_nt_rule_config_schema
from backend.engine.nt_rules.validation import validate_nt_rule_config
from backend.main import create_app
from backend.storage.nt_rule_config_repository import NTRuleConfigRepository


def test_config_schema_contains_all_15_rules_and_matches_defaults():
    schema = get_nt_rule_config_schema()
    rules = {rule["name"]: rule for rule in schema["rules"]}

    assert schema["version"] == 4
    assert len(rules) == 15
    assert set(rules) == set(DEFAULT_RULE_CONFIG)
    assert {
        name: rule["defaults"] for name, rule in rules.items()
    } == DEFAULT_RULE_CONFIG
    assert rules["NT9_PrimaryKeyMissing"]["configurable"] is False
    assert all(
        field["name"] != "excludedColumns"
        for rule in rules.values()
        for field in rule["fields"]
    )
    assert "booleanTypes" not in {
        field["name"] for field in rules["NT3_BooleanNaming"]["fields"]
    }
    assert "caseSensitive" not in {
        field["name"] for field in rules["NT4_AuditColumns"]["fields"]
    }
    for rule_name, field_name in (
        ("NT5_DateTimeColumns", "suffixTypeMappings"),
        ("NT6_SoftDelete", "acceptedStrategies"),
    ):
        field = next(
            item
            for item in rules[rule_name]["fields"]
            if item["name"] == field_name
        )
        allowed_types = next(
            column
            for column in field["columns"]
            if column["name"] == "allowedTypes"
        )
        assert allowed_types["control"] == "DATA_TYPE_MULTI_SELECT"
    missing_outcome = next(
        field
        for field in rules["NT14_BusinessKey"]["fields"]
        if field["name"] == "missingOutcome"
    )
    assert missing_outcome["options"] == ["FAIL"]


def test_config_schema_endpoint_returns_the_versioned_catalog():
    response = TestClient(create_app()).get("/api/v1/nt-rules/config-schema")

    assert response.status_code == 200
    assert response.json()["version"] == 4
    assert len(response.json()["rules"]) == 15


@pytest.mark.parametrize("definition_name", DEFAULT_RULE_CONFIG)
def test_every_default_rule_config_is_valid(definition_name):
    assert validate_nt_rule_config(
        definition_name,
        copy.deepcopy(DEFAULT_RULE_CONFIG[definition_name]),
    ) == []


@pytest.mark.parametrize(
    ("definition_name", "override", "expected_error"),
    [
        ("NT1_TableNaming", {"nameRegex": "["}, "not a valid regex"),
        ("NT1_TableNaming", {"unexpected": True}, "Unknown parameters"),
        (
            "NT11_TableTooWide",
            {"warningThreshold": 90, "failureThreshold": 80},
            "less than or equal",
        ),
        (
            "NT13_NullableRate",
            {"includedColumns": ["id"], "excludedColumns": ["ID"]},
            "overlap",
        ),
        (
            "NT5_DateTimeColumns",
            {"suffixTypeMappings": [{"suffix": "_at"}]},
            "allowedTypes",
        ),
        (
            "NT14_BusinessKey",
            {"missingOutcome": "WARNING"},
            "must be FAIL",
        ),
    ],
)
def test_invalid_rule_config_returns_readable_errors(
    definition_name,
    override,
    expected_error,
):
    config = copy.deepcopy(DEFAULT_RULE_CONFIG[definition_name])
    config.update(override)

    errors = validate_nt_rule_config(definition_name, config)

    assert any(expected_error in error for error in errors)


def test_validator_does_not_raise_for_malformed_list_fields():
    config = copy.deepcopy(DEFAULT_RULE_CONFIG["NT7_TableComment"])
    config["requiredFields"] = 123

    errors = validate_nt_rule_config("NT7_TableComment", config)

    assert errors == ["requiredFields must be a list of non-empty strings"]


def test_legacy_nt_config_is_normalized_to_current_governance_invariants():
    nt3 = NTRuleConfigRepository._effective_config(
        "NT3_BooleanNaming", {"booleanTypes": ["BIT"]}
    )
    nt5 = NTRuleConfigRepository._effective_config(
        "NT5_DateTimeColumns",
        {
            "suffixTypeMappings": [
                {"suffix": "_at", "allowedTypes": ["TIMESTAMPTZ"]}
            ]
        },
    )
    nt14 = NTRuleConfigRepository._effective_config(
        "NT14_BusinessKey",
        {"missingOutcome": "WARNING", "excludedColumns": ["legacy_id"]},
    )
    nt4 = NTRuleConfigRepository._effective_config(
        "NT4_AuditColumns", {"caseSensitive": True}
    )

    assert nt3["booleanTypes"] == ["BOOLEAN", "BOOL"]
    assert nt4["caseSensitive"] is False
    assert nt5["suffixTypeMappings"][0]["allowedTypes"] == ["TIMESTAMPZ"]
    assert nt14["missingOutcome"] == "FAIL"
    assert nt14["excludedColumns"] == []
