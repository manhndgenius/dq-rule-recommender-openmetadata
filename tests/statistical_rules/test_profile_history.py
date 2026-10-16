"""Tests for response-only statistical profile history enrichment."""

from backend.engine.statistical_rules.contracts import (
    LLMSuggestion,
    StatisticalRecommendationResponse,
    StatisticalRuleCandidate,
    SummaryStats,
)
from backend.engine.statistical_rules.profile_history import (
    enrich_recommendation_profile_history,
)


class FakeHistoryClient:
    def __init__(self, profiles):
        self.profiles = profiles
        self.calls = []

    def get_column_profile_history(self, column_fqn, limit=20):
        self.calls.append((column_fqn, limit))
        return self.profiles


def _response(*candidates):
    return StatisticalRecommendationResponse(
        table_fqn="HealthCare.public.patients",
        table_name="patients",
        summary=SummaryStats(),
        recommendations=list(candidates),
    )


def test_enriches_each_rule_with_latest_four_matching_metric_values():
    profiles = [
        {"timestamp": 500, "mean": 50, "median": 45, "stddev": 5},
        {"timestamp": 400, "mean": 40, "median": 35, "stddev": 4},
        {"timestamp": 300, "mean": 30, "median": 25, "stddev": 3},
        {"timestamp": 200, "mean": 20, "median": 15, "stddev": 2},
        {"timestamp": 100, "mean": 10, "median": 5, "stddev": 1},
    ]
    client = FakeHistoryClient(profiles)
    response = _response(
        StatisticalRuleCandidate(
            column="income",
            rule_type="columnValueMeanToBeBetween",
            decision=LLMSuggestion.RECOMMEND,
        ),
        StatisticalRuleCandidate(
            column="income",
            rule_type="columnValueMedianToBeBetween",
            decision=LLMSuggestion.RECOMMEND,
        ),
        StatisticalRuleCandidate(
            column="income",
            rule_type="columnValueStdDevToBeBetween",
            decision=LLMSuggestion.RECOMMEND,
        ),
    )

    enrich_recommendation_profile_history(
        response,
        "healthcare_postgres.HealthCare.public.patients",
        client,
    )

    by_metric = {candidate.profile_metric: candidate for candidate in response.recommendations}
    assert [point.value for point in by_metric["mean"].profile_history] == [20, 30, 40, 50]
    assert [point.value for point in by_metric["median"].profile_history] == [15, 25, 35, 45]
    assert [point.value for point in by_metric["stddev"].profile_history] == [2, 3, 4, 5]
    assert by_metric["mean"].evidence["current_mean"] == 50
    assert by_metric["mean"].evidence["mean_history"] == [
        {"timestamp": 200, "value": 20.0},
        {"timestamp": 300, "value": 30.0},
        {"timestamp": 400, "value": 40.0},
        {"timestamp": 500, "value": 50.0},
    ]
    assert by_metric["median"].evidence["current_median"] == 45
    assert by_metric["stddev"].evidence["current_stddev"] == 5
    assert len(client.calls) == 1
    assert client.calls[0][0].endswith(".patients.income")


def test_missing_or_invalid_metric_values_are_ignored_without_failing_rule():
    client = FakeHistoryClient(
        [
            {"timestamp": 400, "mean": None},
            {"timestamp": 300, "mean": "not-a-number"},
            {"timestamp": 200, "mean": 20.5},
        ]
    )
    response = _response(
        StatisticalRuleCandidate(
            column="income",
            rule_type="columnValueMeanToBeBetween",
            decision=LLMSuggestion.RECOMMEND,
        )
    )

    enrich_recommendation_profile_history(
        response,
        "healthcare_postgres.HealthCare.public.patients",
        client,
    )

    candidate = response.recommendations[0]
    assert candidate.profile_metric == "mean"
    assert [point.model_dump() for point in candidate.profile_history] == [
        {"timestamp": 200, "value": 20.5}
    ]
    assert candidate.evidence["current_mean"] == 20.5
    assert candidate.evidence["mean_history"] == [
        {"timestamp": 200, "value": 20.5}
    ]
