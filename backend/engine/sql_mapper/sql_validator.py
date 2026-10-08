"""SQL Validator - Validate SQL trước khi publish lên OpenMetadata.

Kiểm tra SQL chỉ là read-only SELECT query và an toàn.
"""

import re
from typing import List, Tuple


class SQLValidationError(Exception):
    """Exception raised when SQL validation fails."""
    def __init__(self, message: str, stage: str = "VALIDATION"):
        self.message = message
        self.stage = stage
        super().__init__(message)


class SQLValidator:
    """Validate SQL queries trước khi publish."""

    # SQL keywords that indicate write operations or dangerous operations
    WRITE_KEYWORDS = [
        "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE",
        "CREATE", "ALTER", "GRANT", "REVOKE", "EXECUTE",
        "COPY", "VACUUM", "REINDEX", "CLUSTER", "REFRESH"
    ]

    # Dangerous functions/operations to block
    DANGEROUS_PATTERNS = [
        r"\bpg_\w+\(",  # pg_* functions
        r"\bsystem\b",  # system command
        r"\bset_config\b",  # set_config
        r"\bload_extension\b",  # load_extension
        r"\bxmlparse\b",  # XML parsing with potential XXE
        r"\bxml\b.*\bexternal\b",  # External XML entities
    ]

    def validate(self, sql: str) -> Tuple[bool, str]:
        """
        Validate SQL query.

        Args:
            sql: SQL query string

        Returns:
            Tuple of (is_valid, error_message)

        Raises:
            SQLValidationError: Khi SQL không hợp lệ
        """
        if not sql or not sql.strip():
            raise SQLValidationError("SQL cannot be empty", "VALIDATION")

        sql_upper = sql.upper().strip()

        # 1. Check for write operations
        for keyword in self.WRITE_KEYWORDS:
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                raise SQLValidationError(
                    f"SQL contains write operation: {keyword}",
                    "VALIDATION"
                )

        # 2. Check for dangerous patterns
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, sql_upper, re.IGNORECASE):
                raise SQLValidationError(
                    f"SQL contains dangerous pattern: {pattern}",
                    "VALIDATION"
                )

        # 3. Check that it's a SELECT query
        if not sql_upper.startswith("SELECT") and not sql_upper.startswith("WITH"):
            # WITH is allowed for CTEs
            if sql_upper.startswith("WITH") and "SELECT" not in sql_upper:
                raise SQLValidationError(
                    "CTE must contain a SELECT statement",
                    "VALIDATION"
                )
            if not sql_upper.startswith("SELECT"):
                raise SQLValidationError(
                    "Only SELECT queries are allowed",
                    "VALIDATION"
                )

        # 4. Check for multiple statements (semicolon followed by non-whitespace)
        stmt_pattern = r';\s*\S'
        if re.search(stmt_pattern, sql):
            raise SQLValidationError(
                "SQL contains multiple statements",
                "VALIDATION"
            )

        # 5. Check for unresolved bind parameters (should have been rendered already)
        unresolved = re.findall(r':([a-zA-Z_][a-zA-Z0-9_]*)', sql)
        if unresolved:
            raise SQLValidationError(
                f"Unresolved bind parameters: {', '.join(set(unresolved))}",
                "VALIDATION"
            )

        return True, ""

    def validate_with_params(self, sql: str, params: dict) -> Tuple[bool, str]:
        """
        Validate SQL query and check that all params are used.

        Args:
            sql: SQL query string
            params: Dictionary of parameters

        Returns:
            Tuple of (is_valid, error_message)
        """
        # First validate the SQL structure
        self.validate(sql)

        # Check that all provided params are used in the SQL
        placeholders = set(re.findall(r':([a-zA-Z_][a-zA-Z0-9_]*)', sql))
        param_keys = set(params.keys())

        # Find unused parameters (warning only)
        unused = param_keys - placeholders
        if unused:
            # Just a warning, not an error
            pass

        return True, ""


def validate_sql(sql: str) -> Tuple[bool, str]:
    """
    Convenience function để validate SQL.

    Args:
        sql: SQL query string

    Returns:
        Tuple of (is_valid, error_message)
    """
    validator = SQLValidator()
    try:
        validator.validate(sql)
        return True, ""
    except SQLValidationError as e:
        return False, e.message
