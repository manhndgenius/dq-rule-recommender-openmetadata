"""Statistical rules config."""

from __future__ import annotations

import os


class StatisticalRulesConfig:
    """Config cho statistical rules."""

    # LLM settings
    llm_review_enabled: bool = os.getenv("STAT_LLM_ENABLED", "true").lower() in ("true", "1", "yes")
    llm_timeout_seconds: float = float(os.getenv("STAT_LLM_TIMEOUT", "120"))

    # Feature flag
    enabled: bool = os.getenv("STAT_ENABLED", "true").lower() in ("true", "1", "yes")

    # Numeric datatypes
    numeric_datatypes: tuple = (
        "TINYINT", "SMALLINT", "INT", "INTEGER", "BIGINT",
        "FLOAT", "FLOAT4", "FLOAT8", "DOUBLE", "REAL",
        "DECIMAL", "NUMERIC", "NUMBER",
    )

    def is_numeric_datatype(self, dtype: str) -> bool:
        if not dtype:
            return False
        dtype_upper = dtype.upper()
        for dt in self.numeric_datatypes:
            if dtype_upper.startswith(dt):
                return True
        return False


config = StatisticalRulesConfig()
