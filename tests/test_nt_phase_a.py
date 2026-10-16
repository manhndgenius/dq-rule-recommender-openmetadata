from backend.contracts.nt_execution import NTOutcome, NTRuleResult
from backend.integrations.openmetadata import client as client_module
from backend.integrations.openmetadata.client import OpenMetadataClient
from backend.services.nt_metadata_loader import NTMetadataLoader


class Response:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def json(self):
        return self._payload


def test_nt_result_maps_outcomes_to_openmetadata_statuses():
    assert NTRuleResult(
        definition_name="NT1_TableNaming",
        outcome=NTOutcome.PASS,
        message="ok",
    ).openmetadata_status == "Success"
    assert NTRuleResult(
        definition_name="NT1_TableNaming",
        outcome=NTOutcome.WARNING,
        message="warning",
    ).openmetadata_status == "Failed"
    assert NTRuleResult(
        definition_name="NT1_TableNaming",
        outcome=NTOutcome.FAIL,
        message="failed",
    ).openmetadata_status == "Failed"
    assert NTRuleResult(
        definition_name="NT1_TableNaming",
        outcome=NTOutcome.ERROR,
        message="unavailable",
    ).openmetadata_status == "Aborted"


def test_strict_nt_table_metadata_preserves_missing_values(monkeypatch):
    captured = {}

    def fake_get(url, **kwargs):
        captured["url"] = url
        captured["params"] = kwargs["params"]
        return Response(
            {
                "id": "table-id",
                "name": "encounters",
                "fullyQualifiedName": "svc.db.schema.encounters",
                "tableType": "Regular",
                "description": None,
                "owners": [],
                "domains": [],
                "tags": [],
                "columns": [
                    {
                        "name": "id",
                        "fullyQualifiedName": "svc.db.schema.encounters.id",
                        "dataType": "UUID",
                        "constraint": "PRIMARY_KEY",
                    }
                ],
                "tableConstraints": [
                    {"constraintType": "PRIMARY_KEY", "columns": ["id"]}
                ],
                "profile": None,
            }
        )

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    client = OpenMetadataClient(server_url="http://openmetadata.test/api/v1")
    metadata = client.get_table_metadata_for_nt(
        "svc.db.schema.encounters",
        include_column_profiles=False,
    )

    assert metadata["description"] is None
    assert metadata["owners"] == []
    assert metadata["domains"] == []
    assert metadata["tags"] == []
    assert metadata["columns"][0]["constraint"] == "PRIMARY_KEY"
    assert "domains" in captured["params"]["fields"]
    assert "tableConstraints" in captured["params"]["fields"]


def test_strict_nt_table_metadata_never_returns_demo_fallback(monkeypatch):
    monkeypatch.setattr(
        client_module.requests,
        "get",
        lambda *args, **kwargs: Response({}, status_code=503),
    )
    client = OpenMetadataClient(server_url="http://openmetadata.test/api/v1")

    try:
        client.get_table_metadata_for_nt("svc.db.schema.missing")
        assert False, "Expected a strict OpenMetadata lookup failure"
    except RuntimeError as exc:
        assert "HTTP 503" in str(exc)


def test_nt_definition_pagination_and_filtering(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs["params"].copy())
        if len(calls) == 1:
            return Response(
                {
                    "data": [
                        {"id": "1", "name": "NT1_TableNaming"},
                        {"id": "x", "name": "columnValuesToBeUnique"},
                    ],
                    "paging": {"after": "cursor-1"},
                }
            )
        return Response(
            {
                "data": [{"id": "2", "name": "NT2_ColumnNaming"}],
                "paging": {},
            }
        )

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    client = OpenMetadataClient(server_url="http://openmetadata.test/api/v1")

    definitions = client.list_nt_test_definitions()

    assert [item["name"] for item in definitions] == [
        "NT1_TableNaming",
        "NT2_ColumnNaming",
    ]
    assert calls[1]["after"] == "cursor-1"


def test_table_nt_test_case_pagination_and_filtering(monkeypatch):
    calls = []

    def fake_get(url, **kwargs):
        calls.append(kwargs["params"].copy())
        if len(calls) == 1:
            return Response(
                {
                    "data": [
                        {
                            "id": "tc-1",
                            "testDefinition": {"name": "NT1_TableNaming"},
                        },
                        {
                            "id": "tc-x",
                            "testDefinition": {"name": "tableRowCountToEqual"},
                        },
                    ],
                    "paging": {"after": "cursor-2"},
                }
            )
        return Response(
            {
                "data": [
                    {
                        "id": "tc-2",
                        "testDefinition": {"name": "NT2_ColumnNaming"},
                    }
                ],
                "paging": {},
            }
        )

    monkeypatch.setattr(client_module.requests, "get", fake_get)
    client = OpenMetadataClient(server_url="http://openmetadata.test/api/v1")

    test_cases = client.get_table_nt_test_cases("svc.db.schema.table")

    assert [item["id"] for item in test_cases] == ["tc-1", "tc-2"]
    assert calls[0]["entityLink"] == "<#E::table::svc.db.schema.table>"
    assert calls[1]["after"] == "cursor-2"


def test_publish_nt_result_posts_to_exact_test_case_fqn(monkeypatch):
    captured = {}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["json"] = kwargs["json"]
        return Response({"id": "result-id"})

    monkeypatch.setattr(client_module.requests, "post", fake_post)
    client = OpenMetadataClient(server_url="http://openmetadata.test/api/v1")
    result = NTRuleResult(
        definition_name="NT7_TableComment",
        outcome=NTOutcome.FAIL,
        message="Missing domains and owners",
        observed={"missingFields": ["domains", "owners"]},
        affected_columns=[],
    )

    response = client.add_test_case_result(
        "svc.db.schema.table.NT7 TableComment",
        result,
        timestamp_ms=1_792_100_000_000,
    )

    assert response == {"id": "result-id"}
    assert captured["url"].endswith(
        "/dataQuality/testCases/testCaseResults/"
        "svc.db.schema.table.NT7%20TableComment"
    )
    assert captured["json"]["testCaseStatus"] == "Failed"
    assert captured["json"]["timestamp"] == 1_792_100_000_000
    assert captured["json"]["testResultValue"]


def test_nt_metadata_loader_builds_typed_real_context():
    class ClientStub:
        def get_table_metadata_for_nt(self, table_fqn, include_column_profiles):
            assert table_fqn == "svc.db.schema.table"
            assert include_column_profiles is True
            return {
                "id": "table-id",
                "name": "table",
                "fullyQualifiedName": table_fqn,
                "description": None,
                "owners": [{"name": "owner"}],
                "domains": [{"name": "domain"}],
                "tags": [],
                "columns": [
                    {
                        "name": "created_at",
                        "fullyQualifiedName": f"{table_fqn}.created_at",
                        "dataType": "TIMESTAMP",
                        "description": None,
                        "profile": {"nullProportion": 0.1},
                    }
                ],
                "tableConstraints": [],
                "profile": {"columnCount": 1},
            }

    context = NTMetadataLoader(ClientStub()).load_context(
        "svc.db.schema.table"
    )

    assert context.metadata_source == "OPENMETADATA"
    assert context.description is None
    assert context.owners[0]["name"] == "owner"
    assert context.domains[0]["name"] == "domain"
    assert context.columns[0].profile == {"nullProportion": 0.1}
