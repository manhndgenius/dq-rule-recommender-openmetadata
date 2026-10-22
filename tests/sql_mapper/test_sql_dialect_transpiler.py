import sqlglot
import pytest

from backend.contracts.advanced_rule import GeneratedRule
from backend.contracts.advanced_rule_router import RouterResult
from backend.contracts.table_context import ColumnContext, TableContext
from backend.engine.advanced_rule_service import AdvancedRuleService
from backend.engine.sql_mapper.dialect_transpiler import (
    SQLDialectError,
    resolve_sql_dialect,
    transpile_postgres_sql,
)
from backend.integrations.openmetadata.client import OpenMetadataClient


def test_postgres_sql_bypasses_sqlglot_and_stays_unchanged():
    sql = 'SELECT * FROM "orders" WHERE "completed_at" < "created_at"'

    assert transpile_postgres_sql(sql, "postgres") == sql


@pytest.mark.parametrize(
    ("service_type", "dialect"),
    [
        ("Postgres", "postgres"),
        ("Mysql", "mysql"),
        ("Mssql", "tsql"),
        ("BigQuery", "bigquery"),
        ("Snowflake", "snowflake"),
        ("Trino", "trino"),
    ],
)
def test_openmetadata_service_types_are_normalized(service_type, dialect):
    assert resolve_sql_dialect(service_type) == dialect


@pytest.mark.parametrize("target", ["mysql", "tsql", "bigquery", "snowflake", "trino"])
def test_non_postgres_sql_is_transpiled_and_parses_as_target(target):
    canonical = 'SELECT * FROM "orders" WHERE "completed_at" < "created_at"'

    rendered = transpile_postgres_sql(canonical, target)

    assert rendered
    assert len(sqlglot.parse(rendered, read=target)) == 1


def test_unknown_dialect_and_multiple_statements_fail_closed():
    with pytest.raises(SQLDialectError, match="Unsupported SQL dialect"):
        transpile_postgres_sql("SELECT * FROM orders", "unknown-db")

    with pytest.raises(SQLDialectError, match="exactly one read-only query"):
        transpile_postgres_sql("SELECT * FROM a; SELECT * FROM b", "mysql")


def test_openmetadata_service_type_is_resolved_from_table_service(monkeypatch):
    client = OpenMetadataClient(server_url="http://openmetadata.test/api/v1")
    monkeypatch.setattr(
        client,
        "list_services",
        lambda: [
            {
                "id": "mysql-service-id",
                "name": "sales_mysql",
                "fullyQualifiedName": "sales_mysql",
                "serviceType": "Mysql",
            }
        ],
    )

    assert client.get_database_service_type(
        "sales_mysql",
        {"id": "mysql-service-id", "name": "sales_mysql"},
    ) == "Mysql"


@pytest.mark.asyncio
async def test_advanced_service_transpiles_only_rendered_sql_for_mysql(monkeypatch):
    context = TableContext(
        database_service_type="Mysql",
        sql_dialect="mysql",
        database_name="shop",
        schema_name="shop",
        table_name="orders",
        columns=[
            ColumnContext(name="created_at", data_type="TIMESTAMP"),
            ColumnContext(name="completed_at", data_type="TIMESTAMP"),
        ],
    )
    generated_rule = GeneratedRule(
        rule_type="TEMPORAL",
        target_table="orders",
        columns=["created_at", "completed_at"],
        conditions=[
            {
                "type": "TEMPORAL_ORDER",
                "left": "created_at",
                "operator": "BEFORE_EQUAL",
                "right": "completed_at",
            }
        ],
        reason="Completion follows creation",
    )
    service = AdvancedRuleService()

    async def fake_recommend(*args, **kwargs):
        return RouterResult(candidates=[]), [generated_rule]

    monkeypatch.setattr(service, "recommend", fake_recommend)

    result = await service.recommend_with_sql(context)

    assert result.target_dialect == "mysql"
    assert result.total_sql_failed == 0
    assert result.rules[0].sql.startswith('SELECT * FROM "orders"')
    assert result.rules[0].rendered_sql.startswith("SELECT * FROM `orders`")
