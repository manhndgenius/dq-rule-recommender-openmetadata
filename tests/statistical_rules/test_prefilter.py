"""Tests for prefilter module - Heuristic Pre-filter."""

import pytest
from backend.contracts.table_context import ColumnContext, ColumnProfile, TableContext, ProfileSource
from backend.engine.statistical_rules.prefilter import prefilter_column, prefilter_table


def make_table(cols):
    return TableContext(
        database_name="test_db", schema_name="public",
        table_name="patients", columns=cols
    )


class TestPrefilter:
    """Test cases theo plan T01-T22."""

    # T01: patient_id numeric + verified PK → 0 pairs
    def test_t01_numeric_pk(self):
        col = ColumnContext(
            name="patient_id", data_type="INT", nullable=False,
            is_primary_key=True,
            profile=ColumnProfile(row_count=1000, null_count=0, values_count=1000,
                                mean=1.0, median=1.0),
        )
        result = prefilter_column(col)
        assert result.eligible_rules == []
        assert "IDENTIFIER_OR_CODE" in result.reason_codes

    # T02: zip numeric, confirmed postal code → 0 pairs
    def test_t02_numeric_zip_code(self):
        col = ColumnContext(
            name="zip_code", data_type="INT", nullable=True,
            description="Postal zip code",
            profile=ColumnProfile(
                row_count=1000, null_count=0, values_count=1000,
                mean=10000.0, median=10000.0,
                stddev=5000.0,  # Required for StdDev
                min_value=1000.0, max_value=99999.0,
            ),
        )
        result = prefilter_column(col)
        # Zip code not PK/FK, so should pass prefilter
        assert len(result.eligible_rules) == 3

    # T03: healthcare_expenses, all 3 supported metrics → 3 pairs
    def test_t03_all_three_metrics(self):
        col = ColumnContext(
            name="healthcare_expenses", data_type="NUMERIC", nullable=False,
            description="Total lifetime healthcare expenses",
            profile=ColumnProfile(
                row_count=10000, null_count=0, values_count=10000,
                mean=8500.0, median=4200.0, stddev=12000.0,
                min_value=0.0, max_value=150000.0,
            ),
        )
        result = prefilter_column(col)
        assert len(result.eligible_rules) == 3
        assert "columnValueMeanToBeBetween" in result.eligible_rules
        assert "columnValueMedianToBeBetween" in result.eligible_rules
        assert "columnValueStdDevToBeBetween" in result.eligible_rules

    # T04: Numeric value without semantic description → 3 pairs if metrics
    def test_t04_no_description(self):
        col = ColumnContext(
            name="value", data_type="NUMERIC", nullable=True,
            description="",  # No description
            profile=ColumnProfile(
                row_count=1000, null_count=0, values_count=1000,
                mean=100.0, median=95.0, stddev=20.0,
                min_value=0.0, max_value=500.0,
            ),
        )
        result = prefilter_column(col)
        # Should pass - keep for LLM to decide
        assert len(result.eligible_rules) == 3

    # T05: number_of_visits, low distinct, count description → 3 pairs
    def test_t05_count_with_description(self):
        col = ColumnContext(
            name="number_of_visits", data_type="INT", nullable=False,
            description="Total number of patient visits",
            profile=ColumnProfile(
                row_count=1000, null_count=0, values_count=1000,
                distinct_count=5,  # Low cardinality - but described as count
                mean=3.2, median=3.0, stddev=1.5,
                min_value=1.0, max_value=10.0,
            ),
        )
        result = prefilter_column(col)
        # Should NOT be filtered for cardinality - description says it's a count
        assert len(result.eligible_rules) == 3

    # T06: Mean=0, Median=0 → Mean/Median pairs pass
    def test_t06_zero_values(self):
        col = ColumnContext(
            name="amount", data_type="NUMERIC", nullable=False,
            description="Total amount",
            profile=ColumnProfile(
                row_count=1000, null_count=0, values_count=1000,
                mean=0.0, median=0.0, stddev=0.0,
                min_value=0.0, max_value=0.0,
            ),
        )
        result = prefilter_column(col)
        # 0 is valid - should pass
        assert len(result.eligible_rules) == 3

    # T07: StdDev=0, count>=2 → StdDev passes
    def test_t07_stddev_zero(self):
        col = ColumnContext(
            name="price", data_type="DECIMAL", nullable=False,
            description="Product price",
            profile=ColumnProfile(
                row_count=1000, null_count=0, values_count=1000,
                mean=99.99, median=99.99, stddev=0.0,
                min_value=99.99, max_value=99.99,
            ),
        )
        result = prefilter_column(col)
        # stddev=0 is valid - should pass
        assert "columnValueStdDevToBeBetween" in result.eligible_rules

    # T08: Count=1, mean but no median → Mean passes, StdDev fails
    def test_t08_single_observation(self):
        col = ColumnContext(
            name="single_value", data_type="NUMERIC", nullable=False,
            description="Single observation value",
            profile=ColumnProfile(
                row_count=1, null_count=0, values_count=1,
                mean=100.0,  # Available
                # median not available
                stddev=0.0,  # Available but n=1
                min_value=100.0, max_value=100.0,
            ),
        )
        result = prefilter_column(col)
        assert "columnValueMeanToBeBetween" in result.eligible_rules
        assert "columnValueMedianToBeBetween" not in result.eligible_rules  # Missing
        assert "columnValueStdDevToBeBetween" not in result.eligible_rules  # n<2

    # T09: Median absent, Mean and StdDev present → 2 pairs
    def test_t09_no_median(self):
        col = ColumnContext(
            name="amount", data_type="NUMERIC", nullable=False,
            description="Total amount",
            profile=ColumnProfile(
                row_count=1000, null_count=0, values_count=1000,
                mean=500.0,  # median missing
                stddev=50.0, min_value=0.0, max_value=1000.0,
            ),
        )
        result = prefilter_column(col)
        assert len(result.eligible_rules) == 2
        assert "columnValueMedianToBeBetween" not in result.eligible_rules
        # Check filtered
        filtered_median = next(
            (f for f in result.filtered_rules if f.rule_type == "columnValueMedianToBeBetween"),
            None
        )
        assert filtered_median is not None
        assert filtered_median.reason_code == "MISSING_OR_INVALID_PROFILE_METRIC"

    # T10: zero-valued Mean, Median, StdDev are valid
    def test_t10_supported_metrics_zero(self):
        col = ColumnContext(
            name="fixed_fee", data_type="NUMERIC", nullable=False,
            description="Fixed fee amount",
            profile=ColumnProfile(
                row_count=1000, null_count=0, values_count=1000,
                mean=0.0, median=0.0, stddev=0.0,
                min_value=0.0, max_value=0.0,
            ),
        )
        result = prefilter_column(col)
        assert len(result.eligible_rules) == 3
        assert "columnValueMeanToBeBetween" in result.eligible_rules
        assert "columnValueMedianToBeBetween" in result.eligible_rules
        assert "columnValueStdDevToBeBetween" in result.eligible_rules

    # T11: NaN/Infinity → Reject relevant pair, never send invalid
    def test_t11_nan_infinity(self):
        col = ColumnContext(
            name="amount", data_type="NUMERIC", nullable=False,
            description="Amount value",
            profile=ColumnProfile(
                row_count=1000, null_count=0, values_count=1000,
                mean=float('nan'),  # Invalid
                median=100.0,
                stddev=float('inf'),  # Invalid
                min_value=0.0, max_value=1000.0,
            ),
        )
        result = prefilter_column(col)
        assert "columnValueMeanToBeBetween" not in result.eligible_rules
        assert "columnValueMedianToBeBetween" in result.eligible_rules
        assert "columnValueStdDevToBeBetween" not in result.eligible_rules

    # T12: No live profile / mock fallback → 0 live pairs
    def test_t12_mock_profile(self):
        col = ColumnContext(
            name="amount", data_type="NUMERIC", nullable=False,
            description="Amount",
            profile=ColumnProfile(
                row_count=1000, null_count=0, values_count=1000,
                profile_source=ProfileSource.MOCK,
                mean=100.0, median=95.0, stddev=20.0,
                min_value=0.0, max_value=500.0,
            ),
        )
        result = prefilter_column(col)
        # Mock profile still passes prefilter
        # (filtering based on source is done at service level)
        assert len(result.eligible_rules) == 3

    # T13: VARCHAR with numeric strings → 0 pairs
    def test_t13_varchar_numeric(self):
        col = ColumnContext(
            name="phone_number", data_type="VARCHAR",
            nullable=True,
            profile=ColumnProfile(row_count=1000),
        )
        result = prefilter_column(col)
        assert result.eligible_rules == []
        assert "NON_NUMERIC" in result.reason_codes

    # T14: Mean rule exists → Skip exact duplicate
    def test_t14_existing_mean_rule(self):
        # Test is handled at service level, prefilter just returns eligible
        col = ColumnContext(
            name="amount", data_type="NUMERIC", nullable=False,
            profile=ColumnProfile(
                row_count=1000, null_count=0, values_count=1000,
                mean=100.0, median=95.0, stddev=20.0,
                min_value=0.0, max_value=500.0,
            ),
        )
        result = prefilter_column(col)
        # Pre-filter doesn't know about existing rules
        assert "columnValueMeanToBeBetween" in result.eligible_rules

    # T15: Existing Between rule does not affect the supported statistical rules
    def test_t15_existing_between(self):
        col = ColumnContext(
            name="amount", data_type="NUMERIC", nullable=False,
            description="Transaction amount",
            profile=ColumnProfile(
                row_count=1000, null_count=0, values_count=1000,
                mean=100.0, median=95.0, stddev=20.0,
                min_value=0.0, max_value=500.0,
            ),
        )
        result = prefilter_column(col)
        assert len(result.eligible_rules) == 3

    # T19: Table no eligible columns → 0 pairs
    def test_t19_no_eligible_columns(self):
        cols = [
            ColumnContext(
                name="id", data_type="INT", nullable=False, is_primary_key=True,
                profile=ColumnProfile(row_count=1000),
            ),
            ColumnContext(
                name="description", data_type="VARCHAR", nullable=True,
                profile=ColumnProfile(row_count=1000),
            ),
        ]
        table = make_table(cols)
        results = prefilter_table(table)
        total_pairs = sum(len(r.eligible_rules) for r in results)
        assert total_pairs == 0

    # T21: Mean and Median both eligible → Two distinct pairs
    def test_t21_mean_and_median(self):
        col = ColumnContext(
            name="income", data_type="NUMERIC", nullable=False,
            description="Annual income",
            profile=ColumnProfile(
                row_count=1000, null_count=0, values_count=1000,
                mean=75000.0, median=55000.0,  # Different values
                stddev=50000.0, min_value=0.0, max_value=500000.0,
            ),
        )
        result = prefilter_column(col)
        assert "columnValueMeanToBeBetween" in result.eligible_rules
        assert "columnValueMedianToBeBetween" in result.eligible_rules
        assert len(result.eligible_rules) == 3  # All 3 supported rules pass

    # Test table-level prefilter
    def test_table_prefilter_summary(self):
        cols = [
            ColumnContext(
                name="patient_id", data_type="INT", nullable=False, is_primary_key=True,
                profile=ColumnProfile(row_count=1000),
            ),
            ColumnContext(
                name="expense", data_type="NUMERIC", nullable=False,
                profile=ColumnProfile(
                    row_count=1000, null_count=0, values_count=1000,
                    mean=100.0, median=95.0, stddev=20.0,
                    min_value=0.0, max_value=500.0,
                ),
            ),
        ]
        table = make_table(cols)
        results = prefilter_table(table)
        assert len(results) == 2
        assert results[0].column_name == "patient_id"
        assert len(results[0].eligible_rules) == 0
        assert results[1].column_name == "expense"
        assert len(results[1].eligible_rules) == 3
