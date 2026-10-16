from backend.contracts.generation import GenerationOptions, RuleEngine
from backend.contracts.generation_job import (
    BulkConcurrency,
    CreateGenerationJobRequest,
    GenerationScope,
    JobItemStatus,
    JobStatus,
    ScopeType,
    RetryJobRequest,
)
from fastapi import BackgroundTasks

from backend.api.router.routes_generation_jobs import retry_generation_job
from backend.integrations.openmetadata import client as client_module
from backend.integrations.openmetadata.client import OpenMetadataClient
from backend.services.scope_resolver import ScopeResolver
from backend.storage.generation_job_store import (
    GenerationJobStore,
    generation_job_store,
)


class CatalogClientStub:
    def resolve_table_fqn_strict(self, target):
        return target

    def list_schemas_paginated(self, database_fqn):
        return [
            {"fullyQualifiedName": f"{database_fqn}.a"},
            {"fullyQualifiedName": f"{database_fqn}.b"},
        ]

    def list_tables_paginated(self, schema_fqn):
        return [
            {"fullyQualifiedName": f"{schema_fqn}.t2"},
            {"fullyQualifiedName": f"{schema_fqn}.t1"},
        ]


def _request(scope_type=ScopeType.SCHEMA):
    return CreateGenerationJobRequest(
        scope=GenerationScope(type=scope_type, target_fqn="svc.db.schema"),
        engines=[RuleEngine.BASIC, RuleEngine.STATISTICAL],
        options=GenerationOptions(),
        concurrency=BulkConcurrency(),
    )


def test_scope_resolver_expands_schema_and_sorts_fqns():
    resolver = ScopeResolver(CatalogClientStub())
    assert resolver.resolve(_request().scope) == [
        "svc.db.schema.t1",
        "svc.db.schema.t2",
    ]


def test_scope_resolver_validates_table_fqn_strictly():
    resolver = ScopeResolver(CatalogClientStub())
    scope = GenerationScope(
        type=ScopeType.TABLE,
        target_fqn="svc.db.schema.table",
    )
    assert resolver.resolve(scope) == ["svc.db.schema.table"]


def test_scope_resolver_expands_all_database_schemas():
    resolver = ScopeResolver(CatalogClientStub())
    scope = GenerationScope(type=ScopeType.DATABASE, target_fqn="svc.db")
    assert resolver.resolve(scope) == [
        "svc.db.a.t1",
        "svc.db.a.t2",
        "svc.db.b.t1",
        "svc.db.b.t2",
    ]


def test_job_store_tracks_partial_progress_per_table_and_engine():
    store = GenerationJobStore()
    job = store.create(_request(), ["svc.db.schema.t1"])
    first, second = job.items

    store.start_job(job.job_id)
    store.start_item(job.job_id, first.item_id)
    store.finish_item(
        job.job_id,
        first.item_id,
        JobItemStatus.SUCCESS,
        generated_count=3,
    )
    store.start_item(job.job_id, second.item_id)
    store.finish_item(
        job.job_id,
        second.item_id,
        JobItemStatus.FAILED,
        errors=[{"step": "generate", "message": "LLM unavailable"}],
    )
    store.finish_job(job.job_id)

    summary = store.summary(job.job_id)
    assert summary.status == JobStatus.PARTIAL
    assert summary.processed_items == 2
    assert summary.successful_items == 1
    assert summary.failed_items == 1
    assert summary.generated_rules["BASIC"] == 3


def test_retry_creates_new_job_with_only_failed_items():
    request = CreateGenerationJobRequest(
        scope=GenerationScope(type=ScopeType.TABLE, target_fqn="svc.db.schema.t1"),
        engines=[RuleEngine.BASIC],
    )
    source = generation_job_store.create(request, ["svc.db.schema.t1"])
    item = source.items[0]
    generation_job_store.start_job(source.job_id)
    generation_job_store.start_item(source.job_id, item.item_id)
    generation_job_store.finish_item(
        source.job_id,
        item.item_id,
        JobItemStatus.FAILED,
        errors=[{"step": "generate", "message": "temporary"}],
    )
    generation_job_store.finish_job(source.job_id)

    summary = retry_generation_job(
        source.job_id,
        RetryJobRequest(),
        BackgroundTasks(),
    )
    assert summary.source_job_id == source.job_id
    assert summary.total_items == 1
    assert summary.status == JobStatus.PENDING


def test_strict_catalog_pagination_follows_after_cursor(monkeypatch):
    calls = []

    class Response:
        status_code = 200

        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, **kwargs):
        calls.append(kwargs["params"].copy())
        if len(calls) == 1:
            return Response({
                "data": [{"fullyQualifiedName": "svc.db.schema.t1"}],
                "paging": {"after": "cursor-1"},
            })
        return Response({
            "data": [{"fullyQualifiedName": "svc.db.schema.t2"}],
            "paging": {},
        })

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    client = OpenMetadataClient(server_url="http://openmetadata.test/api/v1")
    tables = client.list_tables_paginated("svc.db.schema")

    assert [table["fullyQualifiedName"] for table in tables] == [
        "svc.db.schema.t1",
        "svc.db.schema.t2",
    ]
    assert calls[1]["after"] == "cursor-1"
