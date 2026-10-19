"""Tests for filtering generated BASIC rules already present in OpenMetadata."""

from types import SimpleNamespace

from backend.api.router import routes_recommendation
from backend.contracts.candidate_rule import CandidateRule
from backend.integrations.openmetadata.client import OpenMetadataClient
from backend.integrations.openmetadata import client as client_module
from backend.services import generation_service as generation_service_module
from backend.validator.existing_rule_reconciler import reconcile_basic_rules


def _candidate(rule_type: str, column: str, parameters=None) -> CandidateRule:
    return CandidateRule(
        rule_type=rule_type,
        target_columns=[column],
        parameters=parameters or {},
        reason="generated",
    )


def test_existing_rule_is_applied_and_duplicate_candidate_is_removed():
    generated = [
        _candidate(
            "columnValuesToBeBetween",
            "age",
            {"minValue": 0, "maxValue": 120},
        ),
        _candidate("columnValuesToBeNotNull", "patient_id"),
    ]
    test_cases = [
        {
            "id": "existing-id",
            "name": "age_between",
            "displayName": "Age range",
            "fullyQualifiedName": "service.db.schema.table.age_between",
            "testDefinition": {"name": "columnValuesToBeBetween"},
            "entityLink": "<#E::table::service.db.schema.table::columns::age>",
            "parameterValues": [
                {"name": "minValue", "value": "18"},
                {"name": "maxValue", "value": "100"},
            ],
        }
    ]

    displayed, reviewable, duplicate_count = reconcile_basic_rules(
        generated, test_cases
    )

    assert duplicate_count == 1
    assert len(displayed) == 2
    assert len(reviewable) == 1
    assert displayed[0].status == "APPLIED"
    assert displayed[0].target_columns == ["age"]
    assert displayed[0].parameters == {"minValue": 18, "maxValue": 100}
    assert reviewable[0].target_columns == ["patient_id"]
    assert reviewable[0].status == "DRAFT"


def test_length_alias_matches_openmetadata_definition():
    generated = [
        _candidate(
            "columnValuesLengthToBeBetween",
            "description",
            {"minLength": 1, "maxLength": 200},
        )
    ]
    test_cases = [
        {
            "name": "description_length",
            "testDefinition": "columnValueLengthsToBeBetween",
            "entityLink": (
                "<#E::table::service.db.schema.table::columns::description>"
            ),
            "parameterValues": [],
        }
    ]

    displayed, reviewable, duplicate_count = reconcile_basic_rules(
        generated, test_cases
    )

    assert duplicate_count == 1
    assert reviewable == []
    assert len(displayed) == 1
    assert displayed[0].rule_type == "columnValueLengthsToBeBetween"
    assert displayed[0].status == "APPLIED"


def test_non_basic_test_case_is_ignored():
    generated = [_candidate("columnValuesToBeNotNull", "patient_id")]
    test_cases = [
        {
            "name": "advanced_sql",
            "testDefinition": "tableCustomSQLQuery",
            "entityLink": "<#E::table::service.db.schema.table>",
        }
    ]

    displayed, reviewable, duplicate_count = reconcile_basic_rules(
        generated, test_cases
    )

    assert duplicate_count == 0
    assert displayed == generated
    assert reviewable == generated


def test_generate_route_returns_applied_but_only_saves_reviewable(monkeypatch):
    generated = [
        _candidate("columnValuesToBeNotNull", "patient_id"),
        _candidate("columnValuesToBeUnique", "patient_id"),
    ]
    existing = {
        "success": True,
        "data": [
            {
                "id": "existing-id",
                "name": "patient_id_not_null",
                "testDefinition": {"name": "columnValuesToBeNotNull"},
                "entityLink": (
                    "<#E::table::service.db.schema.patients::columns::patient_id>"
                ),
            }
        ],
    }
    saved = []
    persisted = []

    monkeypatch.setattr(
        routes_recommendation.openmetadata_client,
        "get_table_context",
        lambda table_name: SimpleNamespace(row_count=10),
    )
    monkeypatch.setattr(
        routes_recommendation.openmetadata_client,
        "get_table_test_cases",
        lambda table_fqn: existing,
    )
    monkeypatch.setattr(
        routes_recommendation.basic_engine,
        "generate_candidates",
        lambda context: generated,
    )
    monkeypatch.setattr(
        routes_recommendation.review_service,
        "save_candidates",
        lambda candidates: saved.extend(candidates),
    )
    monkeypatch.setattr(
        generation_service_module.rule_repository,
        "save_rules",
        lambda **kwargs: persisted.extend(kwargs["rules"]),
    )

    result = routes_recommendation.generate_recommendations(
        routes_recommendation.GenerateRequest(
            table_name="patients",
            table_fqn="service.db.schema.patients",
            engines=["BASIC"],
        )
    )

    assert result["existing_count"] == 1
    assert result["duplicates_filtered"] == 1
    assert result["generated_count"] == 1
    assert [rule.status for rule in result["rules"]] == ["APPLIED", "DRAFT"]
    assert [rule.rule_type for rule in saved] == ["columnValuesToBeUnique"]
    assert [rule["status"] for rule in persisted] == ["APPLIED", "DRAFT"]


def test_table_test_case_query_includes_column_level_tests(monkeypatch):
    captured = {}

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"data": [], "total": 0}

    def fake_get(url, **kwargs):
        captured.update(kwargs.get("params", {}))
        return Response()

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    client = OpenMetadataClient(server_url="http://openmetadata.test/api/v1")

    result = client.get_table_test_cases("service.database.schema.table")

    assert result["success"] is True
    assert captured["includeAllTests"] is True
    assert captured["entityLink"] == "<#E::table::service.database.schema.table>"
