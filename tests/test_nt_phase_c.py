import asyncio
import copy

import pytest
from pydantic import ValidationError

from backend.contracts.nt_execution import (
    CreateNTRunRequest,
    NTMetadataContext,
    NTOutcome,
    NTRunItemStatus,
    NTRunStatus,
    NTTestCaseTarget,
    NTTestDefinition,
    RetryNTRunRequest,
)
from backend.api.router import routes_test_cases
from backend.main import create_app
from backend.engine.nt_rules.config import DEFAULT_RULE_CONFIG
from backend.services.nt_run_service import NTRunService
from backend.services.nt_test_case_mapper import NTTestCaseMapper
from backend.storage.nt_run_store import NTRunStore


def definition(name):
    return NTTestDefinition(
        id=f"id-{name}",
        name=name,
        fully_qualified_name=name,
    )


def target(name, definition_name=None, suffix="deadbeef"):
    definition_name = definition_name or name
    return NTTestCaseTarget(
        id=f"case-{name}",
        name=f"dq_default_{name}_{suffix}",
        fully_qualified_name=f"svc.db.public.encounters.case-{name}",
        test_definition_id=f"id-{definition_name}",
        test_definition_name=definition_name,
        table_fqn="svc.db.public.encounters",
    )


def test_mapper_maps_legacy_cases_but_native_definition_wins():
    definitions = [definition("NT1_TableNaming"), definition("NT9_PrimaryKeyMissing")]
    legacy_nt1 = target("NT1_TableNaming", "tableCustomSQLQuery")
    legacy_nt9 = target("NT9_PrimaryKeyMissing", "tableCustomSQLQuery")
    native_nt9 = NTTestCaseTarget(
        id="native-nt9",
        name="encounters_nt_9_primary_key_missing_ehnn",
        fully_qualified_name="svc.db.public.encounters.native-nt9",
        test_definition_id="id-NT9_PrimaryKeyMissing",
        test_definition_name="NT9_PrimaryKeyMissing",
    )

    mapped = NTTestCaseMapper().map(
        definitions,
        [legacy_nt1, legacy_nt9, native_nt9],
    )

    assert mapped["NT1_TableNaming"].id == legacy_nt1.id
    assert mapped["NT9_PrimaryKeyMissing"].id == native_nt9.id


def test_run_store_separates_execution_status_from_rule_outcome():
    store = NTRunStore()
    item_definition = definition("NT1_TableNaming")
    case = target("NT1_TableNaming")
    run = store.create(
        CreateNTRunRequest(table_fqn="svc.db.public.encounters"),
        [item_definition],
        [case],
    )
    store.start_run(run.run_id)
    store.start_item(run.run_id, run.items[0].item_id)
    from backend.contracts.nt_execution import NTRuleResult

    store.finish_item(
        run.run_id,
        run.items[0].item_id,
        NTRunItemStatus.COMPLETED,
        result=NTRuleResult(
            definition_name=item_definition.name,
            outcome=NTOutcome.FAIL,
            message="Rule failed",
        ),
    )
    store.finish_run(run.run_id)

    summary = store.summary(run.run_id)
    assert summary.status == NTRunStatus.SUCCESS
    assert summary.completed_items == 1
    assert summary.outcome_counts == {"FAIL": 1}


class LoaderStub:
    def __init__(self, definitions, test_cases):
        self.definitions = definitions
        self.test_cases = test_cases

    def load_definitions(self):
        return self.definitions

    def load_test_cases(self, table_fqn):
        assert table_fqn == "svc.db.public.encounters"
        return self.test_cases

    def load_context(self, table_fqn, **kwargs):
        assert kwargs == {
            "include_column_profiles": True,
            "include_catalog_tables": True,
        }
        return NTMetadataContext(
            table_fqn=table_fqn,
            table_name="encounters",
            columns=[],
        )


class ClientStub:
    def __init__(self, fail=False):
        self.fail = fail
        self.published = []

    def add_test_case_result(self, test_case_fqn, result):
        if self.fail:
            raise RuntimeError("publish unavailable")
        self.published.append((test_case_fqn, result))
        return {"status": "ok"}


class ConfigRepositoryStub:
    def __init__(self, configs=None, disabled=None):
        self.configs = copy.deepcopy(configs or DEFAULT_RULE_CONFIG)
        self.disabled = set(disabled or [])

    def list_all(self):
        return [
            {
                "rule_name": name,
                "config": copy.deepcopy(config),
                "enabled": name not in self.disabled,
            }
            for name, config in self.configs.items()
        ]


def test_runner_publishes_only_applied_native_test_cases():
    definitions = [definition("NT1_TableNaming"), definition("NT2_ColumnNaming")]
    mapped_case = target("NT1_TableNaming")
    loader = LoaderStub(definitions, [mapped_case])
    client = ClientStub()
    store = NTRunStore()
    service = NTRunService(
        client,
        store,
        loader=loader,
        config_repository=ConfigRepositoryStub(),
    )
    run = service.prepare(
        CreateNTRunRequest(table_fqn="svc.db.public.encounters")
    )

    service.run(run.run_id)

    summary = store.summary(run.run_id)
    assert summary.status == NTRunStatus.SUCCESS
    assert summary.completed_items == 1
    assert summary.skipped_items == 0
    assert summary.total_items == 1
    assert len(client.published) == 1
    assert client.published[0][0] == mapped_case.fully_qualified_name


def test_runner_marks_publish_failure_as_execution_error():
    item_definition = definition("NT1_TableNaming")
    loader = LoaderStub([item_definition], [target("NT1_TableNaming")])
    store = NTRunStore()
    service = NTRunService(
        ClientStub(fail=True),
        store,
        loader=loader,
        config_repository=ConfigRepositoryStub(),
    )
    run = service.prepare(
        CreateNTRunRequest(table_fqn="svc.db.public.encounters")
    )

    service.run(run.run_id)

    summary = store.summary(run.run_id)
    items = store.items(run.run_id)
    assert summary.status == NTRunStatus.FAILED
    assert summary.error_items == 1
    assert items[0].status == NTRunItemStatus.ERROR
    assert "publish unavailable" in items[0].error


def test_runner_uses_database_rule_config_snapshot():
    item_definition = definition("NT1_TableNaming")
    mapped_case = target("NT1_TableNaming")
    loader = LoaderStub([item_definition], [mapped_case])
    client = ClientStub()
    store = NTRunStore()
    configs = ConfigRepositoryStub(
        {"NT1_TableNaming": {"nameRegex": "^never_matches$"}}
    )
    service = NTRunService(
        client,
        store,
        loader=loader,
        config_repository=configs,
    )
    request = CreateNTRunRequest(table_fqn="svc.db.public.encounters")
    run = service.prepare(request)
    # A later database edit must not change the already-created run.
    configs.configs["NT1_TableNaming"]["nameRegex"] = ".*"

    service.run(run.run_id)

    saved = store.get(run.run_id)
    assert saved.rule_configs["NT1_TableNaming"]["nameRegex"] == "^never_matches$"
    assert client.published[0][1].outcome == NTOutcome.FAIL


def test_invalid_config_is_published_as_aborted_and_is_execution_error():
    item_definition = definition("NT1_TableNaming")
    mapped_case = target("NT1_TableNaming")
    loader = LoaderStub([item_definition], [mapped_case])
    client = ClientStub()
    store = NTRunStore()
    service = NTRunService(
        client,
        store,
        loader=loader,
        config_repository=ConfigRepositoryStub(
            {"NT1_TableNaming": {"nameRegex": "["}}
        ),
    )
    run = service.prepare(
        CreateNTRunRequest(table_fqn="svc.db.public.encounters")
    )

    service.run(run.run_id)

    saved = store.get(run.run_id)
    result = client.published[0][1]
    assert saved.status == NTRunStatus.FAILED
    assert saved.items[0].status == NTRunItemStatus.ERROR
    assert result.outcome == NTOutcome.ERROR
    assert result.openmetadata_status == "Aborted"
    assert result.error_code == "INVALID_RULE_CONFIG"
    assert result.evidence["validationErrors"]


def test_retry_preserves_original_rule_config_snapshot():
    item_definition = definition("NT1_TableNaming")
    loader = LoaderStub([item_definition], [target("NT1_TableNaming")])
    store = NTRunStore()
    configs = ConfigRepositoryStub(
        {"NT1_TableNaming": {"nameRegex": "^encounters$"}}
    )
    service = NTRunService(
        ClientStub(fail=True),
        store,
        loader=loader,
        config_repository=configs,
    )
    source = service.prepare(
        CreateNTRunRequest(table_fqn="svc.db.public.encounters")
    )
    service.run(source.run_id)
    configs.configs["NT1_TableNaming"]["nameRegex"] = "^changed$"

    retry = service.retry(source.run_id, RetryNTRunRequest())

    assert retry.source_run_id == source.run_id
    assert retry.rule_configs == {
        "NT1_TableNaming": {"nameRegex": "^encounters$"},
    }


def test_request_rejects_browser_owned_rule_configs():
    with pytest.raises(ValidationError, match="rule_configs"):
        CreateNTRunRequest(
            table_fqn="svc.db.public.encounters",
            rule_configs={"NT1_TableNaming": {"nameRegex": ".*"}},
        )


def test_prepare_filters_snapshot_to_rules_enabled_in_this_run():
    item_definition = definition("NT1_TableNaming")
    loader = LoaderStub([item_definition], [target("NT1_TableNaming")])
    service = NTRunService(
        ClientStub(),
        NTRunStore(),
        loader=loader,
        config_repository=ConfigRepositoryStub(),
    )

    run = service.prepare(
        CreateNTRunRequest(table_fqn="svc.db.public.encounters")
    )

    assert [item.definition_name for item in run.items] == ["NT1_TableNaming"]
    assert set(run.rule_configs) == {"NT1_TableNaming"}


def test_no_applied_nt_cases_is_a_successful_noop():
    loader = LoaderStub([definition("NT1_TableNaming")], [])
    store = NTRunStore()
    service = NTRunService(
        ClientStub(),
        store,
        loader=loader,
        config_repository=ConfigRepositoryStub(),
    )

    run = service.prepare(
        CreateNTRunRequest(table_fqn="svc.db.public.encounters")
    )
    service.run(run.run_id)

    summary = store.summary(run.run_id)
    assert summary.status == NTRunStatus.SUCCESS
    assert summary.total_items == 0


def test_basic_suite_honors_configured_test_case_subset():
    first = target("NT1_TableNaming")
    first.name = "selected-case"
    second = target("NT2_ColumnNaming")
    second.name = "not-selected-case"
    service = NTRunService(
        ClientStub(),
        NTRunStore(),
        loader=LoaderStub(
            [definition("NT1_TableNaming"), definition("NT2_ColumnNaming")],
            [first, second],
        ),
        config_repository=ConfigRepositoryStub(),
    )

    run = service.prepare(
        CreateNTRunRequest(
            table_fqn="svc.db.public.encounters",
            test_case_names=["selected-case"],
        )
    )

    assert [item.test_case_id for item in run.items] == [first.id]


def test_logical_suite_runs_only_selected_native_nt_cases():
    definitions = [definition("NT1_TableNaming"), definition("NT2_ColumnNaming")]
    selected_case = target("NT1_TableNaming")
    selected_case.name = "selected-case"
    selected_case.table_fqn = "svc.db.public.encounters"

    class LogicalLoader(LoaderStub):
        def load_test_suite_cases(
            self, test_suite_fqn, prefix="NT", test_case_names=None
        ):
            assert test_suite_fqn == "logical-suite"
            assert test_case_names == ["selected-case"]
            return [selected_case]

    store = NTRunStore()
    client = ClientStub()
    service = NTRunService(
        client,
        store,
        loader=LogicalLoader(definitions, []),
        config_repository=ConfigRepositoryStub(),
    )

    run = service.prepare(
        CreateNTRunRequest(
            test_suite_fqn="logical-suite",
            test_case_names=["selected-case"],
        )
    )
    service.run(run.run_id)

    summary = store.summary(run.run_id)
    assert summary.status == NTRunStatus.SUCCESS
    assert summary.test_suite_fqn == "logical-suite"
    assert summary.total_items == 1
    assert client.published[0][0] == selected_case.fully_qualified_name


def test_request_requires_exactly_one_scope():
    with pytest.raises(ValidationError, match="Exactly one"):
        CreateNTRunRequest()
    with pytest.raises(ValidationError, match="Exactly one"):
        CreateNTRunRequest(
            table_fqn="svc.db.schema.table",
            test_suite_fqn="logical-suite",
        )


def test_default_test_case_references_native_nt_definition(monkeypatch):
    captured = []
    monkeypatch.setattr(
        routes_test_cases.openmetadata_client,
        "get_test_definitions",
        lambda prefix: [
            {
                "name": "NT1_TableNaming",
                "displayName": "Table naming",
                "entityType": "TABLE",
                "enabled": True,
            }
        ],
    )
    monkeypatch.setattr(
        routes_test_cases.openmetadata_client,
        "get_table_test_cases",
        lambda table_fqn: {"success": True, "data": [], "total": 0},
    )

    def upsert(payload):
        captured.append(payload)
        return {
            "success": True,
            "data": {"id": "case-id", "fullyQualifiedName": "case-fqn"},
        }

    monkeypatch.setattr(
        routes_test_cases.openmetadata_client,
        "upsert_test_case",
        upsert,
    )

    response = asyncio.run(
        routes_test_cases.create_default_test_cases("svc.db.schema.table")
    )

    assert response["success"] is True
    assert captured[0]["testDefinition"] == "NT1_TableNaming"
    assert captured[0]["parameterValues"] == []


def test_default_test_case_does_not_mutate_an_existing_case(monkeypatch):
    definition_name = "NT1_TableNaming"
    table_fqn = "svc.db.schema.table"
    existing_name = routes_test_cases._generate_test_case_name(
        table_fqn, definition_name
    )
    monkeypatch.setattr(
        routes_test_cases.openmetadata_client,
        "get_test_definitions",
        lambda prefix: [
            {
                "name": definition_name,
                "entityType": "TABLE",
                "enabled": True,
            }
        ],
    )
    monkeypatch.setattr(
        routes_test_cases.openmetadata_client,
        "get_table_test_cases",
        lambda requested_fqn: {
            "success": True,
            "data": [{"id": "existing-id", "name": existing_name}],
            "total": 1,
        },
    )

    def unexpected_upsert(_payload):
        raise AssertionError("existing Test Case must not be updated")

    monkeypatch.setattr(
        routes_test_cases.openmetadata_client,
        "upsert_test_case",
        unexpected_upsert,
    )

    response = asyncio.run(
        routes_test_cases.create_default_test_cases(table_fqn)
    )

    assert response["created_count"] == 0
    assert response["skipped_count"] == 1


def test_phase_c_api_routes_are_registered():
    paths = set(create_app().openapi()["paths"])
    assert "/api/v1/nt-runs" in paths
    assert "/api/v1/nt-runs/{run_id}" in paths
    assert "/api/v1/nt-runs/{run_id}/results" in paths
    assert "/api/v1/nt-runs/{run_id}/retry" in paths
    assert "/api/v1/nt-rules/config-schema" in paths
