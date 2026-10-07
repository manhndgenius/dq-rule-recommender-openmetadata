import json

import pytest

from advanced_rules.cli import main
from advanced_rules.context import ContextBuildError, ContextBuilder, normalize_data_type


def _write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def _documents():
    schema = {
        "database": "HealthCare",
        "schema": "public",
        "tables": [
            {
                "name": "Encounters",
                "description": "Visits",
                "columns": [
                    {"name": "Id", "dataType": "uuid", "primaryKey": True},
                    {"name": "START", "dataType": "timestamp", "description": "Started"},
                    {
                        "name": "STOP",
                        "dataType": "timestamp",
                        "description": "Stopped",
                        "nullable": True,
                    },
                    {
                        "name": "PATIENT",
                        "dataType": "uuid",
                        "foreignKey": "patients.Id",
                    },
                ],
            },
            {
                "name": "patients",
                "columns": [{"name": "Id", "dataType": "uuid", "primaryKey": True}],
            },
        ],
    }
    profile = {
        "database": "HealthCare",
        "tables": [
            {
                "name": "encounters",
                "tableProfile": {"rowCount": 10, "columnCount": 4},
                "columnProfiles": [
                    {
                        "name": "id",
                        "dataType": "uuid",
                        "nullCount": 0,
                        "valuesCount": 10,
                        "distinctCount": 10,
                        "nullProportion": 0,
                        "distinctProportion": 1,
                    },
                    {
                        "name": "start_at",
                        "dataType": "timestamp with time zone",
                        "nullCount": 0,
                        "valuesCount": 10,
                        "distinctCount": 9,
                        "nullProportion": 0,
                        "distinctProportion": 0.9,
                        "min": "2020-01-01T00:00:00Z",
                        "max": "2020-01-02T00:00:00Z",
                    },
                    {
                        "name": "stop_at",
                        "dataType": "timestamptz",
                        "nullCount": 1,
                        "valuesCount": 9,
                        "distinctCount": 9,
                        "nullProportion": 0.1,
                        "distinctProportion": 1,
                    },
                    {
                        "name": "patient",
                        "dataType": "uuid",
                        "nullCount": 0,
                        "valuesCount": 10,
                        "distinctCount": 5,
                        "nullProportion": 0,
                        "distinctProportion": 0.5,
                    },
                ],
            },
            {
                "name": "patients",
                "tableProfile": {"rowCount": 5, "columnCount": 1},
                "columnProfiles": [{"name": "id", "dataType": "uuid", "nullCount": 0}],
            },
        ],
    }
    return schema, profile


@pytest.fixture
def fixture_paths(tmp_path):
    schema, profile = _documents()
    return (
        _write_json(tmp_path / "schema.json", schema),
        _write_json(tmp_path / "profile.json", profile),
    )


def test_exact_alias_enrichment_and_physical_names(fixture_paths):
    context = ContextBuilder(*fixture_paths).build("ENCOUNTERS")

    assert context.table_name == "encounters"
    assert [column.name for column in context.columns] == ["id", "start_at", "stop_at", "patient"]
    assert context.columns[1].description == "Started"
    assert context.columns[2].description == "Stopped"
    assert context.columns[1].data_type == "DATETIME"
    assert context.columns[0].is_primary_key is True
    assert context.columns[0].nullable is False
    assert context.columns[1].nullable is True  # observed non-null is not a schema constraint
    assert context.columns[2].nullable is True


def test_profile_metrics_and_relationship_are_normalized(fixture_paths):
    context = ContextBuilder(*fixture_paths).build("encounters")
    start = context.columns[1]

    assert start.profile.null_ratio == 0
    assert start.profile.distinct_ratio == 0.9
    assert start.profile.min_value == "2020-01-01T00:00:00Z"
    assert start.profile.max_value == "2020-01-02T00:00:00Z"
    assert context.relationships == [
        {
            "from_table": "encounters",
            "from_column": "patient",
            "to_table": "patients",
            "to_column": "id",
        }
    ]


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("varchar(20)", "STRING"),
        ("bigint", "INTEGER"),
        ("double precision", "NUMBER"),
        ("date", "DATE"),
        ("timestamp with time zone", "DATETIME"),
        ("boolean", "BOOLEAN"),
        ("uuid", "UUID"),
    ],
)
def test_type_normalization(source, expected):
    assert normalize_data_type(source) == expected


def test_missing_profile_values_are_safe(fixture_paths):
    schema_path, profile_path = fixture_paths
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["tables"][0]["columnProfiles"][0] = {"name": "id", "dataType": "uuid"}
    _write_json(profile_path, profile)

    column = ContextBuilder(schema_path, profile_path).build("encounters").columns[0]
    assert column.profile.null_count == 0
    assert column.profile.min_value is None
    assert column.profile.max_value is None


def test_unknown_schema_column_does_not_crash_and_warns(tmp_path, caplog):
    schema, profile = _documents()
    schema["tables"][0]["columns"] = schema["tables"][0]["columns"][:-1]
    profile["tables"][0]["columnProfiles"][-1]["dataType"] = "text"
    schema_path = _write_json(tmp_path / "schema.json", schema)
    profile_path = _write_json(tmp_path / "profile.json", profile)

    context = ContextBuilder(schema_path, profile_path).build("encounters")

    patient = context.columns[-1]
    assert patient.name == "patient"
    assert patient.description is None
    assert "No safe schema match" in caplog.text


def test_serialized_context_has_no_raw_rows(fixture_paths):
    payload = ContextBuilder(*fixture_paths).build("encounters").model_dump()
    serialized = json.dumps(payload)
    assert "rows" not in payload
    assert "raw" not in serialized.casefold()


def test_build_all_and_cli_json(fixture_paths, capsys):
    schema_path, profile_path = fixture_paths
    assert len(ContextBuilder(schema_path, profile_path).build()) == 2

    exit_code = main(
        [
            "context",
            "--table",
            "encounters",
            "--schema",
            str(schema_path),
            "--profile",
            str(profile_path),
        ]
    )
    output = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert output["table_name"] == "encounters"
    assert output["columns"][1]["name"] == "start_at"


def test_invalid_document_is_rejected(tmp_path):
    schema_path = _write_json(tmp_path / "schema.json", {"tables": "invalid"})
    profile_path = _write_json(tmp_path / "profile.json", {"tables": []})
    with pytest.raises(ContextBuildError, match="tables.*array"):
        ContextBuilder(schema_path, profile_path)
