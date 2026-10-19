"""Local PostgreSQL integration coverage for generated-rule persistence."""

from __future__ import annotations

import os

import pytest

from backend.api.router.routes_recommendation import (
    GenerateRequest,
    generate_recommendations,
)
from backend.api.router.routes_review import review_rule
from backend.contracts.review import ReviewActionRequest
from backend.storage.db_service import db_service
from backend.storage.migration_runner import MigrationRunner
from backend.storage.rule_repository import RuleRepository


pytestmark = pytest.mark.skipif(
    os.getenv("DQ_TEST_POSTGRES") != "1",
    reason="set DQ_TEST_POSTGRES=1 to run local PostgreSQL integration tests",
)

TABLE_FQN = "integration.db.schema.persistence_test"


@pytest.fixture
def repository():
    repo = RuleRepository()
    with db_service.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM dq_rules WHERE table_fqn=%s", (TABLE_FQN,))
    yield repo
    with db_service.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM dq_rules WHERE table_fqn=%s", (TABLE_FQN,))


def test_migration_is_current_and_creates_only_two_application_tables():
    assert MigrationRunner(db_service).pending() == []
    with db_service.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT tablename
                FROM pg_catalog.pg_tables
                WHERE schemaname='public'
                ORDER BY tablename
                """
            )
            tables = [row[0] for row in cursor.fetchall()]

    assert tables == ["dq_rules", "nt_rule_configs", "schema_migrations"]


def test_rule_survives_reload_and_review_state_survives_regeneration(repository):
    original = {
        "rule_type": "columnValuesToBeNotNull",
        "target_columns": ["email"],
        "parameters": {},
        "engine": "BASIC",
        "confidence": 0.95,
        "reason": "integration test",
        "evidence": {"null_count": 0},
        "status": "DRAFT",
    }

    first = repository.save_rules(TABLE_FQN, "BASIC", [original])
    assert first == {"saved": 1, "inserted": 1, "updated": 0, "preserved": 0}

    loaded = RuleRepository().get_rules(TABLE_FQN, "BASIC")
    assert len(loaded) == 1
    assert loaded[0]["target_columns"] == ["email"]
    rule_id = loaded[0]["id"]

    assert repository.update_status(rule_id, "ACCEPTED") is True
    second = repository.save_rules(TABLE_FQN, "BASIC", [original])
    assert second["preserved"] == 1
    assert RuleRepository().get_rule(rule_id)["status"] == "ACCEPTED"


def test_load_and_review_api_paths_use_postgresql(repository):
    repository.save_rules(
        TABLE_FQN,
        "BASIC",
        [{
            "rule_type": "columnValuesToBeUnique",
            "target_columns": ["customer_id"],
            "engine": "BASIC",
            "confidence": 1.0,
            "reason": "integration test",
            "status": "DRAFT",
        }],
    )

    response = generate_recommendations(
        GenerateRequest(
            table_name="persistence_test",
            table_fqn=TABLE_FQN,
            engines=[],
        )
    )
    assert response["total_rules"] == 1
    rule_id = response["rules"][0]["id"]

    reviewed = review_rule(
        rule_id,
        ReviewActionRequest(action="EDITED", edited_parameters={"value": 7}),
    )
    assert reviewed["rule"]["status"] == "EDITED"
    assert reviewed["rule"]["edited_parameters"] == {"value": 7}

