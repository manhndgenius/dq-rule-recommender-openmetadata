"""SQL Utilities cho SQL Mapper.

Các hàm utility để build SQL an toàn.
"""

from __future__ import annotations

import re
from typing import Sequence


# Pattern để validate identifier (table/column names)
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
# Pattern cho schema.table format
SCHEMA_TABLE_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*$")


class InvalidIdentifierError(ValueError):
    """Raised khi identifier không hợp lệ."""
    pass


def quote_identifier(identifier: str) -> str:
    """Quote một identifier (table hoặc column name) an toàn.

    Args:
        identifier: Tên table hoặc column

    Returns:
        Identifier đã được quote với dấu ngoặc kép

    Raises:
        InvalidIdentifierError: Khi identifier không hợp lệ

    Examples:
        >>> quote_identifier("patients")
        '"patients"'
        >>> quote_identifier("column_name")
        '"column_name"'
        >>> quote_identifier("schema.table")
        '"schema"."table"'
    """
    if not identifier:
        raise InvalidIdentifierError("Identifier cannot be empty")

    # Xử lý schema.table format
    if "." in identifier:
        parts = identifier.split(".")
        if len(parts) != 2:
            raise InvalidIdentifierError(
                f"Invalid schema.table format: {identifier}"
            )
        schema, table = parts
        if not _is_valid_identifier(schema) or not _is_valid_identifier(table):
            raise InvalidIdentifierError(
                f"Invalid characters in schema.table: {identifier}"
            )
        return f'"{schema}"."{table}"'

    # Single identifier
    if not _is_valid_identifier(identifier):
        raise InvalidIdentifierError(
            f"Invalid identifier: {identifier}. "
            f"Must start with letter or underscore, "
            f"contain only alphanumeric and underscore."
        )

    return f'"{identifier}"'


def _is_valid_identifier(name: str) -> bool:
    """Kiểm tra identifier có hợp lệ không."""
    return bool(IDENTIFIER_PATTERN.match(name))


def combine_and(conditions: Sequence[str]) -> str:
    """Kết hợp các conditions với AND.

    Args:
        conditions: Danh sách các condition strings

    Returns:
        Chuỗi kết hợp với AND, hoặc "1=1" nếu empty

    Examples:
        >>> combine_and(["a > 1", "b < 10"])
        '(a > 1 AND b < 10)'
        >>> combine_and([])
        '1=1'
    """
    if not conditions:
        return "1=1"
    if len(conditions) == 1:
        return f"({conditions[0]})"
    return "(" + " AND ".join(conditions) + ")"


def combine_or(conditions: Sequence[str]) -> str:
    """Kết hợp các conditions với OR.

    Args:
        conditions: Danh sách các condition strings

    Returns:
        Chuỗi kết hợp với OR, hoặc "1=0" nếu empty

    Examples:
        >>> combine_or(["a > 1", "b > 5"])
        '(a > 1 OR b > 5)'
        >>> combine_or([])
        '1=0'
    """
    if not conditions:
        return "1=0"
    if len(conditions) == 1:
        return f"({conditions[0]})"
    return "(" + " OR ".join(conditions) + ")"


def build_select_sql(
    table: str,
    columns: str = "*",
    where_clause: str | None = None,
    limit: int | None = None,
) -> str:
    """Build một SELECT query.

    Args:
        table: Tên bảng (đã quoted)
        columns: Các columns cần select (mặc định *)
        where_clause: WHERE clause (không bao gồm từ khóa WHERE)
        limit: Limit số rows (optional)

    Returns:
        SQL query string

    Examples:
        >>> build_select_sql("patients")
        'SELECT * FROM "patients"'
        >>> build_select_sql("patients", "id, name", "age > 18")
        'SELECT id, name FROM "patients" WHERE age > 18'
    """
    parts = [f"SELECT {columns}", f"FROM {table}"]

    if where_clause:
        parts.append(f"WHERE {where_clause}")

    if limit is not None:
        parts.append(f"LIMIT {limit}")

    return " ".join(parts)
