"""Attach OpenMetadata profile history to recommended statistical rules.

This module enriches the API response only. Historical snapshots are never
added to the LLM review context.
"""

from __future__ import annotations

import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Protocol

from backend.engine.statistical_rules.contracts import (
    StatisticalProfilePoint,
    StatisticalRecommendationResponse,
)


RULE_TYPE_TO_PROFILE_METRIC = {
    "columnValueMeanToBeBetween": "mean",
    "columnValueMedianToBeBetween": "median",
    "columnValueStdDevToBeBetween": "stddev",
}


class ColumnProfileHistoryClient(Protocol):
    def get_column_profile_history(
        self, column_fqn: str, limit: int = 20
    ) -> list[dict[str, Any]]: ...


def enrich_recommendation_profile_history(
    response: StatisticalRecommendationResponse,
    table_fqn: str,
    client: ColumnProfileHistoryClient,
    limit: int = 4,
) -> StatisticalRecommendationResponse:
    """Add the latest metric values to RECOMMEND candidates only.

    We select the latest ``limit`` valid values, then return them in ascending
    timestamp order so the frontend can render a time-series chart directly.
    """
    if limit <= 0 or not response.recommendations:
        return response

    columns = sorted(
        {
            candidate.column
            for candidate in response.recommendations
            if candidate.rule_type in RULE_TYPE_TO_PROFILE_METRIC
        }
    )
    if not columns:
        return response

    def fetch(column_name: str) -> tuple[str, list[dict[str, Any]]]:
        column_fqn = f"{table_fqn}.{column_name}"
        return column_name, client.get_column_profile_history(
            column_fqn,
            # Fetch more than four so missing metric values do not hide an
            # older valid point.
            limit=max(20, limit * 5),
        )

    histories: dict[str, list[dict[str, Any]]] = {}
    with ThreadPoolExecutor(max_workers=min(8, len(columns))) as executor:
        for column_name, profiles in executor.map(fetch, columns):
            histories[column_name] = profiles

    for candidate in response.recommendations:
        metric = RULE_TYPE_TO_PROFILE_METRIC.get(candidate.rule_type)
        if not metric:
            continue

        candidate.profile_metric = metric
        newest_points: list[StatisticalProfilePoint] = []
        for profile in histories.get(candidate.column, []):
            timestamp = profile.get("timestamp")
            value = profile.get(metric)
            if timestamp is None or value is None or isinstance(value, bool):
                continue
            try:
                numeric_value = float(value)
                numeric_timestamp = int(timestamp)
            except (TypeError, ValueError, OverflowError):
                continue
            if not math.isfinite(numeric_value):
                continue
            newest_points.append(
                StatisticalProfilePoint(
                    timestamp=numeric_timestamp,
                    value=numeric_value,
                )
            )
            if len(newest_points) == limit:
                break

        candidate.profile_history = sorted(
            newest_points,
            key=lambda point: point.timestamp,
        )
        if candidate.profile_history:
            # Keep the dedicated fields for chart consumers, and also expose
            # the same values as evidence so generic rule UIs do not drop the
            # statistical context.
            candidate.evidence[f"current_{metric}"] = (
                candidate.profile_history[-1].value
            )
            candidate.evidence[f"{metric}_history"] = [
                point.model_dump() for point in candidate.profile_history
            ]

    return response
