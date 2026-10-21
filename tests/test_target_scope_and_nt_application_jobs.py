import asyncio

from fastapi.testclient import TestClient

from backend.api.router import routes_target_scopes
from backend.contracts.batch_job import JobStatus
from backend.contracts.nt_application_job import CreateNtApplicationJobRequest
from backend.contracts.target_scope import SchemasTargetScope
from backend.main import create_app
from backend.services import nt_application_job_runner as runner_module
from backend.services.nt_application_job_runner import NtApplicationJobRunner
from backend.storage.nt_application_job_store import NtApplicationJobStore


def test_shared_scope_preview_returns_server_resolved_snapshot(monkeypatch):
    monkeypatch.setattr(
        routes_target_scopes.scope_resolver,
        "resolve",
        lambda scope: ["svc.db.a.orders", "svc.db.b.customers"],
    )
    response = TestClient(create_app()).post(
        "/api/v1/target-scopes/preview",
        json={
            "scope": {
                "type": "SCHEMAS",
                "schema_fqns": ["svc.db.a", "svc.db.b"],
            }
        },
    )
    assert response.status_code == 200
    assert response.json()["total_tables"] == 2
    assert response.json()["tables"] == [
        "svc.db.a.orders",
        "svc.db.b.customers",
    ]


def test_candidate_preview_accepts_basic_and_advanced(monkeypatch):
    monkeypatch.setattr(
        routes_target_scopes.scope_resolver,
        "resolve",
        lambda scope: ["svc.db.a.orders"],
    )
    client = TestClient(create_app())
    base_payload = {
        "scope": {"type": "TABLES", "table_fqns": ["svc.db.a.orders"]}
    }
    response = client.post(
        "/api/v1/recommendation-jobs/preview",
        json={**base_payload, "engines": ["BASIC", "ADVANCED"]},
    )
    assert response.status_code == 200
    assert response.json()["total_items"] == 2
    assert response.json()["estimated_llm_calls"] == {
        "BASIC": 0,
        "ADVANCED": 4,
    }

    response = client.post(
        "/api/v1/recommendation-jobs/preview",
        json={**base_payload, "engines": ["STATISTICAL"]},
    )
    assert response.status_code == 422
    assert "Only the BASIC and ADVANCED rule engines" in response.text


def test_empty_selection_is_rejected_instead_of_meaning_all_tables():
    response = TestClient(create_app()).post(
        "/api/v1/target-scopes/preview",
        json={"scope": {"type": "TABLES", "table_fqns": []}},
    )
    assert response.status_code == 422


def test_nt_application_job_tracks_partial_table_result(monkeypatch):
    async def fake_apply(table_fqn):
        if table_fqn.endswith("orders"):
            return {
                "success": True,
                "created_count": 15,
                "skipped_count": 0,
                "failed_count": 0,
                "failed": [],
            }
        return {
            "success": False,
            "created_count": 10,
            "skipped_count": 0,
            "failed_count": 5,
            "failed": [{"definition": "NT1", "error": "create failed"}],
        }

    monkeypatch.setattr(runner_module, "create_default_test_cases", fake_apply)
    store = NtApplicationJobStore()
    request = CreateNtApplicationJobRequest(
        scope=SchemasTargetScope(schema_fqns=["svc.db.a"])
    )
    job = store.create(
        request,
        ["svc.db.a.orders", "svc.db.a.customers"],
    )
    asyncio.run(NtApplicationJobRunner(store).run(job.job_id))

    summary = store.summary(job.job_id)
    assert summary.status == JobStatus.PARTIAL
    assert summary.total_tables == 2
    assert summary.processed_tables == 2
    assert summary.successful_tables == 1
    assert summary.partial_tables == 1
    assert summary.created_count == 25
    assert summary.failed_count == 5


def test_new_job_routes_are_registered():
    paths = set(create_app().openapi()["paths"])
    assert "/api/v1/target-scopes/preview" in paths
    assert "/api/v1/recommendation-jobs" in paths
    assert "/api/v1/nt-application-jobs" in paths
    assert "/api/v1/nt-application-jobs/{job_id}" in paths
    assert "/api/v1/advanced-rules/recommend" in paths
    assert "/api/v1/recommendations/statistical/generate" not in paths
