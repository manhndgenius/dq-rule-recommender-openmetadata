"""Publish lifecycle coverage for persisted candidate rules."""

from backend.api.router import routes_datasource
from backend.api.router.routes_datasource import PublishRequest


def test_publish_marks_only_successful_rules_as_applied(monkeypatch):
    stored_rules = {
        "rule-ok": {
            "id": "rule-ok",
            "rule_type": "columnValuesToBeNotNull",
            "target_columns": ["id"],
            "parameters": {},
            "engine": "BASIC",
            "confidence": 1.0,
            "reason": "Identifier is required",
            "status": "ACCEPTED",
        },
        "rule-failed": {
            "id": "rule-failed",
            "rule_type": "columnValuesToBeUnique",
            "target_columns": ["id"],
            "parameters": {},
            "engine": "BASIC",
            "confidence": 1.0,
            "reason": "Identifier should be unique",
            "status": "ACCEPTED",
        },
    }
    updates = []

    monkeypatch.setattr(
        routes_datasource.rule_repository,
        "get_rule",
        lambda rule_id: stored_rules.get(rule_id),
    )
    monkeypatch.setattr(
        routes_datasource.rule_repository,
        "update_status",
        lambda rule_id, status: updates.append((rule_id, status)) or True,
    )
    monkeypatch.setattr(
        routes_datasource.openmetadata_publisher,
        "publish_rules",
        lambda *args, **kwargs: {
            "success": True,
            "published_count": 1,
            "published_test_cases": [
                {"rule_id": "rule-ok", "status": "SUCCESS"}
            ],
            "failed_test_cases": [
                {"rule_id": "rule-failed", "status": "FAILED"}
            ],
        },
    )

    result = routes_datasource.publish_rules(
        PublishRequest(
            table_name="payments",
            table_fqn="service.database.public.payments",
            rule_ids=["rule-ok", "rule-failed"],
        )
    )

    assert updates == [("rule-ok", "APPLIED")]
    assert result["applied_rule_ids"] == ["rule-ok"]
