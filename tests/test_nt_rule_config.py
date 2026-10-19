import copy

import pytest
from fastapi.testclient import TestClient

from backend.engine.nt_rules.config import DEFAULT_RULE_CONFIG
from backend.engine.nt_rules.config_schema import get_nt_rule_config_schema
from backend.engine.nt_rules.validation import validate_nt_rule_config
from backend.main import create_app


def test_config_schema_contains_all_15_rules_and_matches_defaults():
    schema = get_nt_rule_config_schema()
    rules = {rule["name"]: rule for rule in schema["rules"]}

    assert schema["version"] == 1
    assert len(rules) == 15
    assert set(rules) == set(DEFAULT_RULE_CONFIG)
    assert {
        name: rule["defaults"] for name, rule in rules.items()
    } == DEFAULT_RULE_CONFIG
    assert rules["NT9_PrimaryKeyMissing"]["configurable"] is False


def test_config_schema_endpoint_returns_the_versioned_catalog():
    response = TestClient(create_app()).get("/api/v1/nt-rules/config-schema")

    assert response.status_code == 200
    assert response.json()["version"] == 1
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
