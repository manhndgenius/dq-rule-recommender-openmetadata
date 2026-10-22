"""Best-effort SQL dialect compatibility for non-PostgreSQL sources."""

from __future__ import annotations

from typing import Optional

import sqlglot
from sqlglot import ErrorLevel, exp
from sqlglot.errors import ParseError, UnsupportedError


CANONICAL_SQL_DIALECT = "postgres"
SQLGLOT_VERSION = sqlglot.__version__

SERVICE_TYPE_TO_DIALECT = {
    "postgres": "postgres",
    "postgresql": "postgres",
    "mysql": "mysql",
    "mariadb": "mysql",
    "mssql": "tsql",
    "sqlserver": "tsql",
    "sql server": "tsql",
    "bigquery": "bigquery",
    "snowflake": "snowflake",
    "trino": "trino",
    "presto": "presto",
    "redshift": "redshift",
    "databricks": "databricks",
    "oracle": "oracle",
    "athena": "athena",
}


class SQLDialectError(ValueError):
    """Raised when SQL cannot be safely produced for a target dialect."""


def resolve_sql_dialect(service_type: Optional[str]) -> Optional[str]:
    """Map an OpenMetadata database service type to a SQLGlot dialect."""
    if not service_type:
        return None
    normalized = " ".join(str(service_type).strip().lower().split())
    return SERVICE_TYPE_TO_DIALECT.get(normalized)


def _parse_single_query(sql: str, dialect: str) -> exp.Query:
    try:
        expressions = sqlglot.parse(sql, read=dialect, error_level=ErrorLevel.RAISE)
    except ParseError as exc:
        raise SQLDialectError(
            f"SQL cannot be parsed as {dialect}: {exc}"
        ) from exc

    if len(expressions) != 1 or not isinstance(expressions[0], exp.Query):
        raise SQLDialectError("SQL must contain exactly one read-only query")
    return expressions[0]


def transpile_postgres_sql(sql: str, target_dialect: str) -> str:
    """Keep PostgreSQL unchanged; strictly transpile other supported dialects."""
    target = (target_dialect or "").strip().lower()
    if target == CANONICAL_SQL_DIALECT:
        return sql
    if target not in set(SERVICE_TYPE_TO_DIALECT.values()):
        raise SQLDialectError(f"Unsupported SQL dialect: {target or 'unknown'}")

    expression = _parse_single_query(sql, CANONICAL_SQL_DIALECT)
    try:
        rendered = expression.sql(
            dialect=target,
            identify=True,
            unsupported_level=ErrorLevel.RAISE,
        )
    except (UnsupportedError, ValueError) as exc:
        raise SQLDialectError(
            f"Cannot transpile PostgreSQL SQL to {target}: {exc}"
        ) from exc

    # Generating text is not enough: require the target dialect to parse it
    # back into exactly one read-only query before it can be published.
    _parse_single_query(rendered, target)
    return rendered
