import pytest

from backend.contracts.nt_execution import (
    NTColumnMetadata,
    NTMetadataContext,
    NTOutcome,
    NTTestDefinition,
)
from backend.engine.nt_rules.config import (
    DEFAULT_RULE_CONFIG,
    NTRuleConfigResolver,
)
from backend.engine.nt_rules.registry import NT_RULE_REGISTRY, evaluate_nt_rule


def column(
    name,
    data_type="STRING",
    description="documented",
    constraint=None,
):
    return NTColumnMetadata(
        name=name,
        data_type=data_type,
        description=description,
        constraint=constraint,
    )


def context(**overrides):
    values = {
        "table_id": "table-id",
        "table_fqn": "svc.db.public.orders",
        "table_name": "orders",
        "description": "Order business data",
        "owners": [{"name": "data-team", "type": "team"}],
        "domains": [{"name": "Sales", "fullyQualifiedName": "Sales"}],
        "tags": [],
        "columns": [],
        "table_constraints": [],
        "catalog_tables": [],
    }
    values.update(overrides)
    return NTMetadataContext(**values)


def definition(name, **overrides):
    values = {
        "id": f"id-{name}",
        "name": name,
        "fully_qualified_name": name,
    }
    values.update(overrides)
    return NTTestDefinition(**values)


def evaluate(name, metadata, config=None):
    return evaluate_nt_rule(definition(name), metadata, config=config)


def test_registry_contains_all_15_nt_definitions():
    assert set(NT_RULE_REGISTRY) == set(DEFAULT_RULE_CONFIG)
    assert len(NT_RULE_REGISTRY) == 15


def test_config_resolver_merges_definition_level_values():
    item = definition(
        "NT11_TableTooWide",
        rule_config={"warningThreshold": 60},
        parameter_definition=[
            {"name": "failureThreshold", "defaultValue": "90"}
        ],
    )

    resolved = NTRuleConfigResolver().resolve(item)

    assert resolved["warningThreshold"] == 60
    assert resolved["failureThreshold"] == 90


@pytest.mark.parametrize(
    "name,outcome",
    [("valid_table_1", NTOutcome.PASS), ("Invalid-Table", NTOutcome.FAIL)],
)
def test_nt1_table_naming(name, outcome):
    assert evaluate("NT1_TableNaming", context(table_name=name)).outcome == outcome


def test_nt2_column_naming_reports_invalid_columns():
    result = evaluate(
        "NT2_ColumnNaming",
        context(columns=[column("valid_name"), column("Invalid-Name")]),
    )
    assert result.outcome == NTOutcome.FAIL
    assert result.affected_columns == ["Invalid-Name"]


def test_nt3_boolean_naming_only_checks_boolean_columns():
    result = evaluate(
        "NT3_BooleanNaming",
        context(
            columns=[
                column("enabled", "BOOLEAN"),
                column("status", "STRING"),
                column("has_access", "BOOL"),
            ]
        ),
    )
    assert result.outcome == NTOutcome.FAIL
    assert result.affected_columns == ["enabled"]


def test_nt4_audit_columns_uses_configurable_required_list():
    result = evaluate(
        "NT4_AuditColumns",
        context(columns=[column("id"), column("created_at")]),
        {"requiredColumns": ["id", "created_at", "updated_at"], "requireAll": True},
    )
    assert result.outcome == NTOutcome.FAIL
    assert result.affected_columns == ["updated_at"]


def test_nt5_datetime_suffix_type_mapping():
    result = evaluate(
        "NT5_DateTimeColumns",
        context(
            columns=[
                column("created_at", "TIMESTAMP"),
                column("birth_date", "DATE"),
            ]
        ),
    )
    assert result.outcome == NTOutcome.FAIL
    assert result.affected_columns == ["created_at"]


def test_nt6_soft_delete_accepts_either_supported_strategy():
    result = evaluate(
        "NT6_SoftDelete",
        context(columns=[column("deleted_at", "TIMESTAMP WITH TIME ZONE")]),
    )
    assert result.outcome == NTOutcome.PASS


def test_nt7_table_comment_checks_definition_configured_fields():
    result = evaluate(
        "NT7_TableComment",
        context(description="", owners=[], domains=[{"name": "Sales"}]),
        {"requiredFields": ["description", "domains"], "minimumDescriptionLength": 5},
    )
    assert result.outcome == NTOutcome.FAIL
    assert result.observed["missingFields"] == ["description"]


def test_nt8_primary_key_standard_requires_single_uuid_id():
    result = evaluate(
        "NT8_PrimaryKeyStandard",
        context(
            columns=[column("id", "INTEGER", constraint="PRIMARY_KEY")],
        ),
    )
    assert result.outcome == NTOutcome.FAIL
    assert "unexpected_primary_key_type" in result.observed["violations"]


def test_nt9_primary_key_missing_detects_table_constraint():
    result = evaluate(
        "NT9_PrimaryKeyMissing",
        context(
            columns=[column("id", "UUID")],
            table_constraints=[
                {"constraintType": "PRIMARY_KEY", "columns": ["id"]}
            ],
        ),
    )
    assert result.outcome == NTOutcome.PASS


def test_nt10_column_description_skips_default_audit_columns():
    result = evaluate(
        "NT10_ColumnDescription",
        context(
            columns=[
                column("id", "UUID", description=None),
                column("customer_name", description=None),
            ]
        ),
    )
    assert result.outcome == NTOutcome.FAIL
    assert result.affected_columns == ["customer_name"]


@pytest.mark.parametrize(
    "count,outcome",
    [
        (50, NTOutcome.PASS),
        (51, NTOutcome.WARNING),
        (80, NTOutcome.WARNING),
        (81, NTOutcome.FAIL),
    ],
)
def test_nt11_table_width_bands(count, outcome):
    columns = [column(f"column_{index}") for index in range(count)]
    assert evaluate("NT11_TableTooWide", context(columns=columns)).outcome == outcome


def test_nt12_domain_owner_validates_allowed_domain():
    result = evaluate(
        "NT12_DomainOwner",
        context(domains=[{"name": "Unknown"}]),
        {
            "requiredFields": ["domains", "owners"],
            "allowedDomains": ["Sales"],
            "minimumOwnerCount": 1,
            "allowedOwnerTypes": [],
        },
    )
    assert result.outcome == NTOutcome.FAIL
    assert result.observed["invalidDomains"] == ["unknown"]


@pytest.mark.parametrize(
    "not_null_count,outcome",
    [
        (5, NTOutcome.PASS),
        (3, NTOutcome.WARNING),
        (1, NTOutcome.FAIL),
    ],
)
def test_nt13_nullable_column_rate_bands(not_null_count, outcome):
    columns = [
        column(
            f"column_{index}",
            constraint="NOT_NULL" if index < not_null_count else None,
        )
        for index in range(10)
    ]
    assert evaluate("NT13_NullableRate", context(columns=columns)).outcome == outcome


def test_nt14_missing_business_key_is_warning():
    result = evaluate(
        "NT14_BusinessKey",
        context(columns=[column("id"), column("description")]),
    )
    assert result.outcome == NTOutcome.WARNING


def test_nt16_duplicate_table_requires_catalog_and_detects_other_schema():
    unavailable = evaluate("NT16_DuplicateTable", context())
    assert unavailable.outcome == NTOutcome.ERROR
    assert unavailable.error_code == "CATALOG_SCOPE_NOT_LOADED"

    result = evaluate(
        "NT16_DuplicateTable",
        context(
            catalog_tables=[
                {
                    "name": "orders",
                    "fullyQualifiedName": "svc.db.public.orders",
                },
                {
                    "name": "orders",
                    "fullyQualifiedName": "svc.db.archive.orders",
                },
            ]
        ),
    )
    assert result.outcome == NTOutcome.FAIL
    assert result.observed["duplicateTables"] == ["svc.db.archive.orders"]
