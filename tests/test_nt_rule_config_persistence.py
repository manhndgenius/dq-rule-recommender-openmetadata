"""Local PostgreSQL integration tests for NT rule configuration APIs."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from backend.contracts.nt_execution import (
    CreateNTRunRequest,
    NTTestCaseTarget,
    NTTestDefinition,
)
from backend.main import create_app
from backend.services.nt_run_service import NTRunService
from backend.storage.db_service import db_service
from backend.storage.nt_rule_config_repository import (
    InvalidNTRuleConfigError,
    NTRuleConfigConflictError,
    NTRuleConfigRepository,
)
from backend.storage.nt_run_store import NTRunStore


pytestmark = pytest.mark.skipif(
    os.getenv("DQ_TEST_POSTGRES") != "1",
    reason="set DQ_TEST_POSTGRES=1 to run local PostgreSQL integration tests",
)

RULE_NAME = "NT11_TableTooWide"


@pytest.fixture(autouse=True)
def clean_config():
    with db_service.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM nt_rule_configs WHERE rule_name=%s",
                (RULE_NAME,),
            )
    yield
    with db_service.connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM nt_rule_configs WHERE rule_name=%s",
                (RULE_NAME,),
            )


def test_repository_merges_defaults_versions_updates_and_resets():
    repository = NTRuleConfigRepository()

    initial = repository.get(RULE_NAME)
    assert initial["persisted"] is False
    assert initial["version"] == 0
    assert initial["config"]["warningThreshold"] == 50

    saved = repository.upsert(
        RULE_NAME,
        {"warningThreshold": 60},
        expected_version=0,
        updated_by="integration-user",
    )
    assert saved["version"] == 1
    assert saved["override"] == {"warningThreshold": 60}
    assert saved["config"] == {
        "warningThreshold": 60,
        "failureThreshold": 80,
        "excludedColumns": [],
    }

    updated = repository.upsert(
        RULE_NAME,
        {
            "warningThreshold": 65,
            "failureThreshold": 90,
            "excludedColumns": ["metadata"],
        },
        expected_version=1,
    )
    assert updated["version"] == 2
    assert updated["config"]["failureThreshold"] == 90

    with pytest.raises(NTRuleConfigConflictError) as conflict:
        repository.upsert(
            RULE_NAME,
            {"warningThreshold": 70},
            expected_version=1,
        )
    assert conflict.value.current_version == 2

    reset = repository.delete(RULE_NAME, expected_version=2)
    assert reset["persisted"] is False
    assert reset["version"] == 0
    assert reset["config"]["warningThreshold"] == 50


def test_repository_rejects_invalid_config_without_writing():
    repository = NTRuleConfigRepository()

    with pytest.raises(InvalidNTRuleConfigError):
        repository.upsert(
            RULE_NAME,
            {"warningThreshold": 90, "failureThreshold": 80},
            expected_version=0,
        )

    assert repository.get(RULE_NAME)["persisted"] is False


def test_config_api_crud_validation_and_conflict():
    client = TestClient(create_app())

    listed = client.get("/api/v1/nt-rules/configs")
    assert listed.status_code == 200
    assert listed.json()["total"] == 15

    created = client.put(
        f"/api/v1/nt-rules/{RULE_NAME}/config",
        json={
            "config": {"warningThreshold": 60},
            "expected_version": 0,
            "updated_by": "api-user",
        },
    )
    assert created.status_code == 200
    assert created.json()["version"] == 1
    assert created.json()["config"]["failureThreshold"] == 80

    stale = client.put(
        f"/api/v1/nt-rules/{RULE_NAME}/config",
        json={
            "config": {"warningThreshold": 61},
            "expected_version": 0,
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["current_version"] == 1

    invalid = client.put(
        f"/api/v1/nt-rules/{RULE_NAME}/config",
        json={
            "config": {"warningThreshold": 90, "failureThreshold": 80},
            "expected_version": 1,
        },
    )
    assert invalid.status_code == 422

    fetched = client.get(f"/api/v1/nt-rules/{RULE_NAME}/config")
    assert fetched.status_code == 200
    assert fetched.json()["version"] == 1

    deleted = client.delete(
        f"/api/v1/nt-rules/{RULE_NAME}/config",
        params={"expected_version": 1},
    )
    assert deleted.status_code == 200
    assert deleted.json()["persisted"] is False
    assert deleted.json()["config"]["warningThreshold"] == 50


def test_config_api_returns_not_found_for_unknown_rule():
    response = TestClient(create_app()).get(
        "/api/v1/nt-rules/NT999_Unknown/config"
    )

    assert response.status_code == 404


def test_nt_run_snapshots_effective_config_from_postgresql():
    repository = NTRuleConfigRepository()
    saved = repository.upsert(
        RULE_NAME,
        {"warningThreshold": 61},
        expected_version=0,
    )

    definition = NTTestDefinition(
        id="definition-11",
        name=RULE_NAME,
        fully_qualified_name=RULE_NAME,
    )
    test_case = NTTestCaseTarget(
        id="case-11",
        name=f"dq_default_{RULE_NAME}_deadbeef",
        fully_qualified_name="svc.db.schema.table.case-11",
        test_definition_name="tableCustomSQLQuery",
    )

    class Loader:
        @staticmethod
        def load_definitions():
            return [definition]

        @staticmethod
        def load_test_cases(_table_fqn):
            return [test_case]

    service = NTRunService(
        client=object(),
        store=NTRunStore(),
        loader=Loader(),
        config_repository=repository,
    )
    run = service.prepare(CreateNTRunRequest(table_fqn="svc.db.schema.table"))

    assert run.rule_configs[RULE_NAME] == saved["config"]
    assert run.rule_configs[RULE_NAME]["warningThreshold"] == 61
    assert run.rule_configs[RULE_NAME]["failureThreshold"] == 80
