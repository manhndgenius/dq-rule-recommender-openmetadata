from backend.contracts.nt_execution import (
    CreateNTRunRequest,
    NTMetadataContext,
    NTOutcome,
    NTRunItemStatus,
    NTRunStatus,
    NTTestCaseTarget,
    NTTestDefinition,
)
from backend.main import create_app
from backend.services.nt_run_service import NTRunService
from backend.services.nt_test_case_mapper import NTTestCaseMapper
from backend.storage.nt_run_store import NTRunStore


def definition(name):
    return NTTestDefinition(
        id=f"id-{name}",
        name=name,
        fully_qualified_name=name,
    )


def target(name, definition_name="tableCustomSQLQuery", suffix="deadbeef"):
    return NTTestCaseTarget(
        id=f"case-{name}",
        name=f"dq_default_{name}_{suffix}",
        fully_qualified_name=f"svc.db.public.encounters.case-{name}",
        test_definition_id=f"id-{definition_name}",
        test_definition_name=definition_name,
    )


def test_mapper_maps_legacy_cases_but_native_definition_wins():
    definitions = [definition("NT1_TableNaming"), definition("NT9_PrimaryKeyMissing")]
    legacy_nt1 = target("NT1_TableNaming")
    legacy_nt9 = target("NT9_PrimaryKeyMissing")
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
        {item_definition.name: case},
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


def test_runner_publishes_each_mapped_result_and_skips_missing_case():
    definitions = [definition("NT1_TableNaming"), definition("NT2_ColumnNaming")]
    mapped_case = target("NT1_TableNaming")
    loader = LoaderStub(definitions, [mapped_case])
    client = ClientStub()
    store = NTRunStore()
    service = NTRunService(client, store, loader=loader)
    run = service.prepare(
        CreateNTRunRequest(table_fqn="svc.db.public.encounters")
    )

    service.run(run.run_id)

    summary = store.summary(run.run_id)
    assert summary.status == NTRunStatus.PARTIAL
    assert summary.completed_items == 1
    assert summary.skipped_items == 1
    assert len(client.published) == 1
    assert client.published[0][0] == mapped_case.fully_qualified_name


def test_runner_marks_publish_failure_as_execution_error():
    item_definition = definition("NT1_TableNaming")
    loader = LoaderStub([item_definition], [target("NT1_TableNaming")])
    store = NTRunStore()
    service = NTRunService(ClientStub(fail=True), store, loader=loader)
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


def test_phase_c_api_routes_are_registered():
    paths = set(create_app().openapi()["paths"])
    assert "/api/v1/nt-runs" in paths
    assert "/api/v1/nt-runs/{run_id}" in paths
    assert "/api/v1/nt-runs/{run_id}/results" in paths
    assert "/api/v1/nt-runs/{run_id}/retry" in paths
