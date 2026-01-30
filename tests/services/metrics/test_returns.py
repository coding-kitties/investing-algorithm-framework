"""
Tests for returns calculation functions.

Tests cover:
- get_monthly_returns
- get_yearly_returns
- get_percentage_winning_months
- get_best_month
- get_worst_month
- get_best_year
- get_worst_year
- get_average_monthly_return
- get_average_monthly_return_winning_months
- get_average_monthly_return_losing_months
- get_average_yearly_return
- get_total_return
- get_total_loss
- get_total_growth
- get_percentage_winning_years
- get_final_value
- get_cumulative_return
- get_cumulative_return_series
"""

from datetime import datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework.services.metrics.returns import (
    get_monthly_returns,
    get_yearly_returns,
    get_percentage_winning_months,
    get_best_month,
    get_worst_month,
    get_best_year,
    get_worst_year,
    get_average_monthly_return,
    get_average_monthly_return_winning_months,
    get_average_monthly_return_losing_months,
    get_average_yearly_return,
    get_total_return,
    get_total_loss,
    get_total_growth,
    get_percentage_winning_years,
    get_final_value,
    get_cumulative_return,
    get_cumulative_return_series,
)


class MockSnapshot:
    """Mock PortfolioSnapshot class for testing."""

    def __init__(self, total_value: float, created_at: datetime):
        self.total_value = total_value
        self.created_at = created_at

    def get_total_value(self):
        return self.total_value

    def get_created_at(self):
        return self.created_at


class TestGetMonthlyReturns(TestCase):
    """Tests for get_monthly_returns function."""

    def _create_monthly_snapshots(self, values, start_year=2023, start_month=1):
        """Helper to create snapshots with monthly intervals."""
        snapshots = []
        for i, value in enumerate(values):
            month = (start_month - 1 + i) % 12 + 1
            year = start_year + (start_month - 1 + i) // 12
            date = datetime(year, month, 15, tzinfo=timezone.utc)
            snapshots.append(MockSnapshot(value, date))
        return snapshots

    def test_monthly_returns_basic(self):
        """Test basic monthly returns calculation."""
        # 3 months of data
        values = [1000, 1100, 1050]  # +10%, -4.55%
        snapshots = self._create_monthly_snapshots(values)

        result = get_monthly_returns(snapshots)

        # Should have 2 returns (n-1 for n months)
        self.assertEqual(len(result), 2)
        # First return: (1100-1000)/1000 = 0.10
        self.assertAlmostEqual(result[0][0], 0.10, delta=0.01)

    def test_monthly_returns_empty(self):
        """Test with empty snapshot list."""
        result = get_monthly_returns([])
        self.assertEqual(result, [])

    def test_monthly_returns_single_month(self):
        """Test with single month data."""
        snapshots = [MockSnapshot(1000, datetime(2023, 1, 15, tzinfo=timezone.utc))]
        result = get_monthly_returns(snapshots)
        self.assertEqual(result, [])

    def test_monthly_returns_positive_trend(self):
        """Test with consistently positive monthly returns."""
        # 5% monthly growth for 6 months
        values = [1000 * (1.05 ** i) for i in range(7)]
        snapshots = self._create_monthly_snapshots(values)

        result = get_monthly_returns(snapshots)

        # All returns should be approximately 5%
        for return_val, _ in result:
            self.assertAlmostEqual(return_val, 0.05, delta=0.01)

    def test_monthly_returns_negative_trend(self):
        """Test with consistently negative monthly returns."""
        # 5% monthly decline for 6 months
        values = [1000 * (0.95 ** i) for i in range(7)]
        snapshots = self._create_monthly_snapshots(values)

        result = get_monthly_returns(snapshots)

        # All returns should be approximately -5%
        for return_val, _ in result:
            self.assertAlmostEqual(return_val, -0.05, delta=0.01)

    def test_monthly_returns_mixed(self):
        """Test with mixed positive and negative months."""
        values = [1000, 1100, 1000, 1150, 1050]
        snapshots = self._create_monthly_snapshots(values)

        result = get_monthly_returns(snapshots)

        # Returns: +10%, -9.09%, +15%, -8.7%
        self.assertGreater(result[0][0], 0)  # Positive
        self.assertLess(result[1][0], 0)     # Negative
        self.assertGreater(result[2][0], 0)  # Positive
        self.assertLess(result[3][0], 0)     # Negative


class TestGetYearlyReturns(TestCase):
    """Tests for get_yearly_returns function."""

    def _create_yearly_snapshots(self, values, start_year=2020):
        """Helper to create snapshots with yearly intervals."""
        return [
            MockSnapshot(value, datetime(start_year + i, 6, 15, tzinfo=timezone.utc))
            for i, value in enumerate(values)
        ]

    def test_yearly_returns_basic(self):
        """Test basic yearly returns calculation."""
        # 3 years: 2020, 2021, 2022
        values = [1000, 1200, 1100]  # +20%, -8.33%
        snapshots = self._create_yearly_snapshots(values)

        result = get_yearly_returns(snapshots)

        # Should have returns for complete years
        self.assertGreater(len(result), 0)

    def test_yearly_returns_empty(self):
        """Test with empty snapshot list."""
        result = get_yearly_returns([])
        self.assertEqual(result, [])

    def test_yearly_returns_single_year(self):
        """Test with data from single year only."""
        snapshots = [MockSnapshot(1000, datetime(2023, 6, 15, tzinfo=timezone.utc))]
        result = get_yearly_returns(snapshots)
        self.assertEqual(result, [])

    def test_yearly_returns_multi_year_growth(self):
        """Test with multi-year growth."""
        # 4 years with 10% annual growth
        values = [1000, 1100, 1210, 1331, 1464]
        snapshots = self._create_yearly_snapshots(values)

        result = get_yearly_returns(snapshots)

        # Returns should be approximately 10%
        for return_val, _ in result:
            self.assertAlmostEqual(return_val, 0.10, delta=0.02)


class TestGetPercentageWinningMonths(TestCase):
    """Tests for get_percentage_winning_months function."""

    def _create_monthly_snapshots(self, values, start_year=2023, start_month=1):
        """Helper to create snapshots with monthly intervals."""
        snapshots = []
        for i, value in enumerate(values):
            month = (start_month - 1 + i) % 12 + 1
            year = start_year + (start_month - 1 + i) // 12
            date = datetime(year, month, 15, tzinfo=timezone.utc)
            snapshots.append(MockSnapshot(value, date))
        return snapshots

    def test_percentage_winning_months_all_winning(self):
        """Test when all months are winning."""
        values = [1000, 1100, 1200, 1300, 1400]
        snapshots = self._create_monthly_snapshots(values)

        result = get_percentage_winning_months(snapshots)

        self.assertEqual(result, 1.0)

    def test_percentage_winning_months_all_losing(self):
        """Test when all months are losing."""
        values = [1000, 900, 800, 700, 600]
        snapshots = self._create_monthly_snapshots(values)

        result = get_percentage_winning_months(snapshots)

        self.assertEqual(result, 0.0)

    def test_percentage_winning_months_mixed(self):
        """Test with mixed winning and losing months."""
        values = [1000, 1100, 1000, 1150, 1050]  # 2 up, 2 down
        snapshots = self._create_monthly_snapshots(values)

        result = get_percentage_winning_months(snapshots)

        self.assertEqual(result, 0.5)  # 50%

    def test_percentage_winning_months_empty(self):
        """Test with empty snapshot list."""
        result = get_percentage_winning_months([])
        self.assertEqual(result, 0.0)


class TestGetBestWorstMonth(TestCase):
    """Tests for get_best_month and get_worst_month functions."""

    def _create_monthly_snapshots(self, values, start_year=2023, start_month=1):
        """Helper to create snapshots with monthly intervals."""
        snapshots = []
        for i, value in enumerate(values):
            month = (start_month - 1 + i) % 12 + 1
            year = start_year + (start_month - 1 + i) // 12
            date = datetime(year, month, 15, tzinfo=timezone.utc)
            snapshots.append(MockSnapshot(value, date))
        return snapshots

    def test_best_month_basic(self):
        """Test basic best month identification."""
        # Returns: +10%, -20%, +30%, -5%
        values = [1000, 1100, 880, 1144, 1086.8]
        snapshots = self._create_monthly_snapshots(values)

        return_val, month = get_best_month(snapshots)

        # Best month is +30%
        self.assertGreater(return_val, 0.25)

    def test_worst_month_basic(self):
        """Test basic worst month identification."""
        # Returns: +10%, -20%, +30%, -5%
        values = [1000, 1100, 880, 1144, 1086.8]
        snapshots = self._create_monthly_snapshots(values)

        return_val, month = get_worst_month(snapshots)

        # Worst month is -20%
        self.assertLess(return_val, -0.15)

    def test_best_month_empty(self):
        """Test best month with empty list."""
        return_val, month = get_best_month([])
        self.assertEqual(return_val, 0.0)
        self.assertIsNone(month)

    def test_worst_month_empty(self):
        """Test worst month with empty list."""
        return_val, month = get_worst_month([])
        self.assertEqual(return_val, 0.0)
        self.assertIsNone(month)


class TestGetBestWorstYear(TestCase):
    """Tests for get_best_year and get_worst_year functions."""

    def _create_yearly_snapshots(self, values, start_year=2020):
        """Helper to create snapshots with yearly intervals."""
        return [
            MockSnapshot(value, datetime(start_year + i, 6, 15, tzinfo=timezone.utc))
            for i, value in enumerate(values)
        ]

    def test_best_year_basic(self):
        """Test basic best year identification."""
        # Returns: +20%, -10%, +30%
        values = [1000, 1200, 1080, 1404]
        snapshots = self._create_yearly_snapshots(values)

        result = get_best_year(snapshots)

        if result[0] is not None:
            # Best year has highest return
            self.assertGreater(result[0], 0.2)

    def test_worst_year_basic(self):
        """Test basic worst year identification."""
        # Returns: +20%, -10%, +30%
        values = [1000, 1200, 1080, 1404]
        snapshots = self._create_yearly_snapshots(values)

        result = get_worst_year(snapshots)

        if result[0] is not None:
            # Worst year has lowest return
            self.assertLess(result[0], 0)

    def test_best_year_empty(self):
        """Test best year with empty list."""
        result = get_best_year([])
        self.assertIsNone(result[0])
        self.assertIsNone(result[1])

    def test_worst_year_empty(self):
        """Test worst year with empty list."""
        result = get_worst_year([])
        self.assertIsNone(result[0])
        self.assertIsNone(result[1])


class TestGetAverageMonthlyReturn(TestCase):
    """Tests for average monthly return functions."""

    def _create_monthly_snapshots(self, values, start_year=2023, start_month=1):
        """Helper to create snapshots with monthly intervals."""
        snapshots = []
        for i, value in enumerate(values):
            month = (start_month - 1 + i) % 12 + 1
            year = start_year + (start_month - 1 + i) // 12
            date = datetime(year, month, 15, tzinfo=timezone.utc)
            snapshots.append(MockSnapshot(value, date))
        return snapshots

    def test_average_monthly_return_basic(self):
        """Test basic average monthly return."""
        # Consistent 5% monthly growth
        values = [1000 * (1.05 ** i) for i in range(7)]
        snapshots = self._create_monthly_snapshots(values)

        result = get_average_monthly_return(snapshots)

        self.assertAlmostEqual(result, 0.05, delta=0.01)

    def test_average_monthly_return_empty(self):
        """Test with empty list."""
        result = get_average_monthly_return([])
        self.assertEqual(result, 0.0)

    def test_average_monthly_return_winning_months(self):
        """Test average return for winning months only."""
        # +10%, -5%, +15%, -10% -> avg of +10% and +15% = 12.5%
        values = [1000, 1100, 1045, 1201.75, 1081.575]
        snapshots = self._create_monthly_snapshots(values)

        result = get_average_monthly_return_winning_months(snapshots)

        self.assertGreater(result, 0)

    def test_average_monthly_return_losing_months(self):
        """Test average return for losing months only."""
        # +10%, -5%, +15%, -10%
        values = [1000, 1100, 1045, 1201.75, 1081.575]
        snapshots = self._create_monthly_snapshots(values)

        result = get_average_monthly_return_losing_months(snapshots)

        self.assertLess(result, 0)

    def test_average_monthly_return_winning_months_no_winners(self):
        """Test when no winning months exist."""
        values = [1000, 900, 800, 700]
        snapshots = self._create_monthly_snapshots(values)

        result = get_average_monthly_return_winning_months(snapshots)

        self.assertEqual(result, 0.0)

    def test_average_monthly_return_losing_months_no_losers(self):
        """Test when no losing months exist."""
        values = [1000, 1100, 1200, 1300]
        snapshots = self._create_monthly_snapshots(values)

        result = get_average_monthly_return_losing_months(snapshots)

        self.assertEqual(result, 0.0)


class TestGetAverageYearlyReturn(TestCase):
    """Tests for get_average_yearly_return function."""

    def _create_yearly_snapshots(self, values, start_year=2020):
        """Helper to create snapshots with yearly intervals."""
        return [
            MockSnapshot(value, datetime(start_year + i, 6, 15, tzinfo=timezone.utc))
            for i, value in enumerate(values)
        ]

    def test_average_yearly_return_basic(self):
        """Test basic average yearly return."""
        # Consistent 10% annual growth
        values = [1000 * (1.10 ** i) for i in range(5)]
        snapshots = self._create_yearly_snapshots(values)

        result = get_average_yearly_return(snapshots)

        # Should be approximately 10%
        self.assertAlmostEqual(result, 0.10, delta=0.02)

    def test_average_yearly_return_empty(self):
        """Test with empty list."""
        result = get_average_yearly_return([])
        self.assertEqual(result, 0.0)


class TestGetTotalReturn(TestCase):
    """Tests for get_total_return function."""

    def _create_snapshots(self, values, start_date=None):
        """Helper to create snapshots."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            MockSnapshot(value, start_date + timedelta(days=i * 30))
            for i, value in enumerate(values)
        ]

    def test_total_return_positive(self):
        """Test positive total return."""
        values = [1000, 1100, 1200, 1500]
        snapshots = self._create_snapshots(values)

        absolute, percentage = get_total_return(snapshots)

        self.assertEqual(absolute, 500)  # 1500 - 1000
        self.assertEqual(percentage, 0.5)  # 50%

    def test_total_return_negative(self):
        """Test negative total return."""
        values = [1000, 900, 800, 700]
        snapshots = self._create_snapshots(values)

        absolute, percentage = get_total_return(snapshots)

        self.assertEqual(absolute, -300)  # 700 - 1000
        self.assertEqual(percentage, -0.3)  # -30%

    def test_total_return_breakeven(self):
        """Test breakeven total return."""
        values = [1000, 1200, 800, 1000]
        snapshots = self._create_snapshots(values)

        absolute, percentage = get_total_return(snapshots)

        self.assertEqual(absolute, 0)
        self.assertEqual(percentage, 0.0)

    def test_total_return_empty(self):
        """Test with empty list."""
        absolute, percentage = get_total_return([])
        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_total_return_single_snapshot(self):
        """Test with single snapshot."""
        snapshots = [MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc))]
        absolute, percentage = get_total_return(snapshots)
        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_total_return_zero_initial_value(self):
        """Test with zero initial value."""
        values = [0, 100, 200]
        snapshots = self._create_snapshots(values)

        absolute, percentage = get_total_return(snapshots)

        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)


class TestGetTotalLoss(TestCase):
    """Tests for get_total_loss function."""

    def _create_snapshots(self, values, start_date=None):
        """Helper to create snapshots."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            MockSnapshot(value, start_date + timedelta(days=i * 30))
            for i, value in enumerate(values)
        ]

    def test_total_loss_with_loss(self):
        """Test total loss when there is a loss."""
        values = [1000, 900, 800, 700]
        snapshots = self._create_snapshots(values)

        absolute, percentage = get_total_loss(snapshots)

        self.assertEqual(absolute, -300)  # 700 - 1000
        self.assertEqual(percentage, -0.3)  # -30%

    def test_total_loss_with_profit(self):
        """Test total loss when there is a profit (should return 0)."""
        values = [1000, 1100, 1200, 1300]
        snapshots = self._create_snapshots(values)

        absolute, percentage = get_total_loss(snapshots)

        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_total_loss_breakeven(self):
        """Test total loss at breakeven (should return 0)."""
        values = [1000, 1200, 800, 1000]
        snapshots = self._create_snapshots(values)

        absolute, percentage = get_total_loss(snapshots)

        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)

    def test_total_loss_empty(self):
        """Test with empty list."""
        absolute, percentage = get_total_loss([])
        self.assertEqual(absolute, 0.0)
        self.assertEqual(percentage, 0.0)


class TestGetTotalGrowth(TestCase):
    """Tests for get_total_growth function."""

    def _create_snapshots(self, values, start_date=None):
        """Helper to create snapshots."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            MockSnapshot(value, start_date + timedelta(days=i * 30))
            for i, value in enumerate(values)
        ]

    def test_total_growth_positive(self):
        """Test positive total growth."""
        values = [1000, 1200, 1500]
        snapshots = self._create_snapshots(values)

        growth, growth_pct = get_total_growth(snapshots)

        self.assertEqual(growth, 500)  # 1500 - 1000
        self.assertEqual(growth_pct, 0.5)  # 50%

    def test_total_growth_negative(self):
        """Test negative total growth (decline)."""
        values = [1000, 800, 600]
        snapshots = self._create_snapshots(values)

        growth, growth_pct = get_total_growth(snapshots)

        self.assertEqual(growth, -400)  # 600 - 1000
        self.assertEqual(growth_pct, -0.4)  # -40%

    def test_total_growth_empty(self):
        """Test with empty list."""
        growth, growth_pct = get_total_growth([])
        self.assertEqual(growth, 0.0)
        self.assertEqual(growth_pct, 0.0)


class TestGetPercentageWinningYears(TestCase):
    """Tests for get_percentage_winning_years function."""

    def _create_yearly_snapshots(self, values, start_year=2020):
        """Helper to create snapshots with yearly intervals."""
        return [
            MockSnapshot(value, datetime(start_year + i, 6, 15, tzinfo=timezone.utc))
            for i, value in enumerate(values)
        ]

    def test_percentage_winning_years_all_winning(self):
        """Test when all years are winning."""
        values = [1000, 1100, 1200, 1300, 1400]
        snapshots = self._create_yearly_snapshots(values)

        result = get_percentage_winning_years(snapshots)

        # All years should be winning
        self.assertEqual(result, 1.0)

    def test_percentage_winning_years_all_losing(self):
        """Test when all years are losing."""
        values = [1000, 900, 800, 700, 600]
        snapshots = self._create_yearly_snapshots(values)

        result = get_percentage_winning_years(snapshots)

        self.assertEqual(result, 0.0)

    def test_percentage_winning_years_empty(self):
        """Test with empty list."""
        result = get_percentage_winning_years([])
        self.assertEqual(result, 0.0)


class TestGetFinalValue(TestCase):
    """Tests for get_final_value function."""

    def _create_snapshots(self, values, start_date=None):
        """Helper to create snapshots."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            MockSnapshot(value, start_date + timedelta(days=i * 30))
            for i, value in enumerate(values)
        ]

    def test_final_value_basic(self):
        """Test basic final value retrieval."""
        values = [1000, 1200, 1500]
        snapshots = self._create_snapshots(values)

        result = get_final_value(snapshots)

        self.assertEqual(result, 1500)

    def test_final_value_empty(self):
        """Test with empty list."""
        result = get_final_value([])
        self.assertEqual(result, 0.0)

    def test_final_value_single(self):
        """Test with single snapshot."""
        snapshots = [MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc))]
        result = get_final_value(snapshots)
        self.assertEqual(result, 1000)


class TestGetCumulativeReturn(TestCase):
    """Tests for get_cumulative_return function."""

    def _create_snapshots(self, values, start_date=None):
        """Helper to create snapshots."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            MockSnapshot(value, start_date + timedelta(days=i * 30))
            for i, value in enumerate(values)
        ]

    def test_cumulative_return_positive(self):
        """Test positive cumulative return."""
        values = [1000, 1100, 1200, 1500]
        snapshots = self._create_snapshots(values)

        result = get_cumulative_return(snapshots)

        # (1500 / 1000) - 1 = 0.5 (50%)
        self.assertEqual(result, 0.5)

    def test_cumulative_return_negative(self):
        """Test negative cumulative return."""
        values = [1000, 900, 800, 700]
        snapshots = self._create_snapshots(values)

        result = get_cumulative_return(snapshots)

        # (700 / 1000) - 1 = -0.3 (-30%)
        self.assertAlmostEqual(result, -0.3, places=10)

    def test_cumulative_return_zero(self):
        """Test zero cumulative return (breakeven)."""
        values = [1000, 1200, 800, 1000]
        snapshots = self._create_snapshots(values)

        result = get_cumulative_return(snapshots)

        self.assertEqual(result, 0.0)

    def test_cumulative_return_single_snapshot(self):
        """Test with single snapshot."""
        snapshots = [MockSnapshot(1000, datetime(2024, 1, 1, tzinfo=timezone.utc))]
        result = get_cumulative_return(snapshots)
        self.assertEqual(result, 0.0)

    def test_cumulative_return_empty(self):
        """Test with empty list."""
        result = get_cumulative_return([])
        self.assertEqual(result, 0.0)

    def test_cumulative_return_zero_start_value(self):
        """Test with zero start value."""
        values = [0, 100, 200]
        snapshots = self._create_snapshots(values)

        result = get_cumulative_return(snapshots)

        self.assertEqual(result, 0.0)

    def test_cumulative_return_doubling(self):
        """Test 100% cumulative return (doubling)."""
        values = [1000, 1500, 2000]
        snapshots = self._create_snapshots(values)

        result = get_cumulative_return(snapshots)

        self.assertEqual(result, 1.0)  # 100%


class TestGetCumulativeReturnSeries(TestCase):
    """Tests for get_cumulative_return_series function."""

    def _create_snapshots(self, values, start_date=None):
        """Helper to create snapshots."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            MockSnapshot(value, start_date + timedelta(days=i * 30))
            for i, value in enumerate(values)
        ]

    def test_cumulative_return_series_basic(self):
        """Test basic cumulative return series."""
        values = [1000, 1100, 1200, 1500]
        snapshots = self._create_snapshots(values)

        result = get_cumulative_return_series(snapshots)

        # First point: (1000/1000) - 1 = 0
        self.assertAlmostEqual(result[0][0], 0.0, places=10)
        # Second point: (1100/1000) - 1 = 0.1
        self.assertAlmostEqual(result[1][0], 0.1, places=10)
        # Third point: (1200/1000) - 1 = 0.2
        self.assertAlmostEqual(result[2][0], 0.2, places=10)
        # Fourth point: (1500/1000) - 1 = 0.5
        self.assertAlmostEqual(result[3][0], 0.5, places=10)

    def test_cumulative_return_series_length(self):
        """Test that series has correct length."""
        values = [1000, 1100, 1200, 1500, 1600]
        snapshots = self._create_snapshots(values)

        result = get_cumulative_return_series(snapshots)

        self.assertEqual(len(result), 5)

    def test_cumulative_return_series_timestamps(self):
        """Test that timestamps are preserved."""
        start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        values = [1000, 1100, 1200]
        snapshots = self._create_snapshots(values, start_date)

        result = get_cumulative_return_series(snapshots)

        self.assertEqual(result[0][1], start_date)
        self.assertEqual(result[1][1], start_date + timedelta(days=30))
        self.assertEqual(result[2][1], start_date + timedelta(days=60))

    def test_cumulative_return_series_negative(self):
        """Test series with negative cumulative returns."""
        values = [1000, 900, 800, 700]
        snapshots = self._create_snapshots(values)

        result = get_cumulative_return_series(snapshots)

        # All points after first should be negative
        self.assertAlmostEqual(result[0][0], 0.0, places=10)
        self.assertAlmostEqual(result[1][0], -0.1, places=10)
        self.assertAlmostEqual(result[2][0], -0.2, places=10)
        self.assertAlmostEqual(result[3][0], -0.3, places=10)

    def test_cumulative_return_series_zero_initial_raises(self):
        """Test that zero initial value raises ValueError."""
        values = [0, 100, 200]
        snapshots = self._create_snapshots(values)

        with self.assertRaises(ValueError):
            get_cumulative_return_series(snapshots)


class TestReturnsIntegration(TestCase):
    """Integration tests for returns functions."""

    def _create_snapshots(self, values, start_date=None):
        """Helper to create snapshots."""
        if start_date is None:
            start_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
        return [
            MockSnapshot(value, start_date + timedelta(days=i * 30))
            for i, value in enumerate(values)
        ]

    def test_total_return_equals_cumulative_return(self):
        """Verify total return percentage equals cumulative return."""
        values = [1000, 1200, 1100, 1500]
        snapshots = self._create_snapshots(values)

        _, total_pct = get_total_return(snapshots)
        cumulative = get_cumulative_return(snapshots)

        self.assertEqual(total_pct, cumulative)

    def test_total_growth_equals_total_return(self):
        """Verify total growth equals total return."""
        values = [1000, 1200, 1100, 1500]
        snapshots = self._create_snapshots(values)

        return_abs, return_pct = get_total_return(snapshots)
        growth_abs, growth_pct = get_total_growth(snapshots)

        self.assertEqual(return_abs, growth_abs)
        self.assertEqual(return_pct, growth_pct)

    def test_final_value_consistent_with_total_return(self):
        """Verify final value is consistent with total return calculation."""
        values = [1000, 1200, 1100, 1500]
        snapshots = self._create_snapshots(values)

        final = get_final_value(snapshots)
        absolute_return, _ = get_total_return(snapshots)

        # final = initial + absolute_return
        self.assertEqual(final, 1000 + absolute_return)

    def test_cumulative_series_final_equals_cumulative_return(self):
        """Verify last point of series equals cumulative return."""
        values = [1000, 1200, 1100, 1500]
        snapshots = self._create_snapshots(values)

        series = get_cumulative_return_series(snapshots)
        cumulative = get_cumulative_return(snapshots)

        self.assertEqual(series[-1][0], cumulative)

