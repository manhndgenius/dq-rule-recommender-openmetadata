"""SQL Renderer - Render bind parameters thành literal SQL.

Sử dụng SQLAlchemy để escape và render bind parameters thành SQL literal an toàn.
"""

import re
from typing import Dict, Any, Optional


class SQLRenderError(Exception):
    """Exception raised when SQL rendering fails."""
    pass


class SQLRenderer:
    """Render SQL với bind parameters thành executable SQL literal."""

    def __init__(self, dialect: str = "postgresql"):
        self.dialect = dialect

    def render(self, sql: str, params: Dict[str, Any]) -> str:
        """
        Render SQL với bind parameters thành SQL executable.

        Args:
            sql: SQL string với placeholder dạng :param_name
            params: Dictionary mapping param_name -> value

        Returns:
            SQL string với các placeholder đã được thay bằng literal values

        Raises:
            SQLRenderError: Khi thiếu parameter hoặc có lỗi rendering
        """
        if not sql or not sql.strip():
            raise SQLRenderError("SQL cannot be empty")

        # Find all placeholders in format :param_name
        placeholders = set(re.findall(r':([a-zA-Z_][a-zA-Z0-9_]*)', sql))

        # Check for missing parameters
        missing = placeholders - set(params.keys())
        if missing:
            raise SQLRenderError(f"Missing bind parameters: {', '.join(missing)}")

        # Check for unused parameters (warning only, not an error)
        unused = set(params.keys()) - placeholders
        if unused:
            pass  # Just a warning, continue

        # Render each placeholder
        result = sql
        for param_name in placeholders:
            value = params[param_name]
            literal = self._value_to_literal(value)
            result = result.replace(f":{param_name}", literal)

        # Check for unresolved placeholders
        remaining = set(re.findall(r':([a-zA-Z_][a-zA-Z0-9_]*)', result))
        if remaining:
            raise SQLRenderError(f"Unresolved parameters after rendering: {', '.join(remaining)}")

        return result

    def _value_to_literal(self, value: Any) -> str:
        """Convert a Python value to SQL literal string."""
        if value is None:
            return "NULL"

        if isinstance(value, bool):
            return "TRUE" if value else "FALSE"

        if isinstance(value, int):
            return str(value)

        if isinstance(value, float):
            return str(value)

        if isinstance(value, (list, tuple)):
            # For IN clauses, render as comma-separated literals
            literals = [self._value_to_literal(v) for v in value]
            return "(" + ", ".join(literals) + ")"

        if isinstance(value, str):
            # Escape single quotes by doubling them
            escaped = value.replace("'", "''")
            return f"'{escaped}'"

        # For other types, convert to string and quote
        escaped = str(value).replace("'", "''")
        return f"'{escaped}'"


def render_sql_literal(sql: str, params: Dict[str, Any], dialect: str = "postgresql") -> str:
    """
    Convenience function để render SQL với bind parameters.

    Args:
        sql: SQL string với placeholder dạng :param_name
        params: Dictionary mapping param_name -> value
        dialect: SQL dialect (default: postgresql)

    Returns:
        SQL string với các placeholder đã được thay bằng literal values

    Raises:
        SQLRenderError: Khi thiếu parameter hoặc có lỗi rendering
    """
    renderer = SQLRenderer(dialect)
    return renderer.render(sql, params)
