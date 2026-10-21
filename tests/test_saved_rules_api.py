"""Coverage for browsing PostgreSQL rules without starting generation."""

from backend.api.router import routes_recommendation
from backend.storage.rule_repository import RuleRepository


def test_saved_rules_endpoint_uses_read_only_repository(monkeypatch):
    expected = {
        "items": [],
        "total": 0,
        "tables": [],
        "status_counts": {},
    }
    monkeypatch.setattr(
        routes_recommendation.rule_repository,
        "list_saved_rules",
        lambda: expected,
    )

    assert routes_recommendation.get_saved_rules() == expected


def test_candidate_keeps_table_identity_for_multi_table_ui():
    candidate = RuleRepository._candidate(
        {
            "rule_id": "rule-1",
            "rule_type": "columnValuesToBeNotNull",
            "target_columns": ["id"],
            "reason": "Identifier should be present",
            "table_name": "encounters",
            "table_fqn": "service.database.public.encounters",
        }
    )

    assert candidate["table_name"] == "encounters"
    assert candidate["table_fqn"] == "service.database.public.encounters"


def test_candidate_keeps_persisted_status_and_edited_parameters():
    candidate = RuleRepository._candidate(
        {
            "rule_id": "rule-accepted",
            "rule_type": "columnValuesToBeBetween",
            "target_columns": ["amount"],
            "reason": "Expected business range",
            "status": "ACCEPTED",
            "parameters": {"minValue": 0, "maxValue": 100},
            "edited_parameters": {"minValue": 10, "maxValue": 90},
            "table_name": "payments",
            "table_fqn": "service.database.public.payments",
        }
    )

    assert candidate["status"] == "ACCEPTED"
    assert candidate["parameters"] == {"minValue": 10, "maxValue": 90}
