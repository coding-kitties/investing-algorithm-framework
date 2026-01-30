"""
Tests for generate_backtest_summary_metrics function.

Tests cover:
- safe_weighted_mean helper function
- _compound_percentage_returns helper function
- generate_backtest_summary_metrics main function
- Aggregation logic verification for different metric types
"""

import unittest
from unittest.mock import MagicMock

from investing_algorithm_framework.domain.backtesting.combine_backtests import (
    safe_weighted_mean,
    _compound_percentage_returns,
    generate_backtest_summary_metrics,
)


def create_mock_backtest_metrics(
    total_net_gain=100.0,
    total_net_gain_percentage=10.0,
    gross_loss=-50.0,
    total_loss_percentage=-5.0,
    total_growth=100.0,
    total_growth_percentage=10.0,
    gross_profit=150.0,
    cagr=0.12,
    sharpe_ratio=1.5,
    sortino_ratio=2.0,
    calmar_ratio=1.2,
    profit_factor=2.0,
    annual_volatility=0.15,
    max_drawdown=-0.10,
    max_drawdown_duration=30,
    trades_per_year=50,
    win_rate=60.0,
    current_win_rate=55.0,
    win_loss_ratio=1.5,
    current_win_loss_ratio=1.4,
    number_of_trades=10,
    number_of_trades_closed=8,
    cumulative_exposure=0.8,
    exposure_ratio=0.75,
    average_trade_return=12.5,
    average_trade_return_percentage=1.25,
    average_trade_loss=-25.0,
    average_trade_loss_percentage=-2.5,
    average_trade_gain=50.0,
    average_trade_gain_percentage=5.0,
    total_number_of_days=365,
):
    """Helper to create mock BacktestMetrics objects."""
    metrics = MagicMock()
    metrics.total_net_gain = total_net_gain
    metrics.total_net_gain_percentage = total_net_gain_percentage
    metrics.gross_loss = gross_loss
    metrics.total_loss_percentage = total_loss_percentage
    metrics.total_growth = total_growth
    metrics.total_growth_percentage = total_growth_percentage
    metrics.gross_profit = gross_profit
    metrics.cagr = cagr
    metrics.sharpe_ratio = sharpe_ratio
    metrics.sortino_ratio = sortino_ratio
    metrics.calmar_ratio = calmar_ratio
    metrics.profit_factor = profit_factor
    metrics.annual_volatility = annual_volatility
    metrics.max_drawdown = max_drawdown
    metrics.max_drawdown_duration = max_drawdown_duration
    metrics.trades_per_year = trades_per_year
    metrics.win_rate = win_rate
    metrics.current_win_rate = current_win_rate
    metrics.win_loss_ratio = win_loss_ratio
    metrics.current_win_loss_ratio = current_win_loss_ratio
    metrics.number_of_trades = number_of_trades
    metrics.number_of_trades_closed = number_of_trades_closed
    metrics.cumulative_exposure = cumulative_exposure
    metrics.exposure_ratio = exposure_ratio
    metrics.average_trade_return = average_trade_return
    metrics.average_trade_return_percentage = average_trade_return_percentage
    metrics.average_trade_loss = average_trade_loss
    metrics.average_trade_loss_percentage = average_trade_loss_percentage
    metrics.average_trade_gain = average_trade_gain
    metrics.average_trade_gain_percentage = average_trade_gain_percentage
    metrics.total_number_of_days = total_number_of_days
    return metrics


class TestSafeWeightedMean(unittest.TestCase):
    """Tests for safe_weighted_mean helper function."""

    def test_basic_weighted_mean(self):
        """Test basic weighted mean calculation."""
        values = [10, 20, 30]
        weights = [1, 1, 1]

        result = safe_weighted_mean(values, weights)

        # Equal weights: (10 + 20 + 30) / 3 = 20
        self.assertEqual(result, 20.0)

    def test_unequal_weights(self):
        """Test weighted mean with unequal weights."""
        values = [10, 20]
        weights = [1, 3]

        result = safe_weighted_mean(values, weights)

        # (10*1 + 20*3) / (1+3) = 70 / 4 = 17.5
        self.assertEqual(result, 17.5)

    def test_ignores_none_values(self):
        """Test that None values are ignored."""
        values = [10, None, 30]
        weights = [1, 1, 1]

        result = safe_weighted_mean(values, weights)

        # Only 10 and 30: (10 + 30) / 2 = 20
        self.assertEqual(result, 20.0)

    def test_ignores_none_weights(self):
        """Test that None weights are ignored."""
        values = [10, 20, 30]
        weights = [1, None, 1]

        result = safe_weighted_mean(values, weights)

        # Only 10 and 30: (10 + 30) / 2 = 20
        self.assertEqual(result, 20.0)

    def test_ignores_zero_weights(self):
        """Test that zero weights are ignored."""
        values = [10, 20, 30]
        weights = [1, 0, 1]

        result = safe_weighted_mean(values, weights)

        # Zero weight ignored: (10 + 30) / 2 = 20
        self.assertEqual(result, 20.0)

    def test_ignores_negative_weights(self):
        """Test that negative weights are ignored."""
        values = [10, 20, 30]
        weights = [1, -1, 1]

        result = safe_weighted_mean(values, weights)

        # Negative weight ignored: (10 + 30) / 2 = 20
        self.assertEqual(result, 20.0)

    def test_empty_lists(self):
        """Test with empty lists."""
        result = safe_weighted_mean([], [])
        self.assertIsNone(result)

    def test_all_none_values(self):
        """Test when all values are None."""
        values = [None, None, None]
        weights = [1, 1, 1]

        result = safe_weighted_mean(values, weights)

        self.assertIsNone(result)

    def test_all_zero_weights(self):
        """Test when all weights are zero."""
        values = [10, 20, 30]
        weights = [0, 0, 0]

        result = safe_weighted_mean(values, weights)

        self.assertIsNone(result)

    def test_single_value(self):
        """Test with single value."""
        values = [42]
        weights = [1]

        result = safe_weighted_mean(values, weights)

        self.assertEqual(result, 42.0)


class TestCompoundPercentageReturns(unittest.TestCase):
    """Tests for _compound_percentage_returns helper function."""

    def test_basic_compounding(self):
        """Test basic percentage compounding."""
        # 10% followed by 5%
        # (1 + 0.10) * (1 + 0.05) - 1 = 1.155 - 1 = 0.155 = 15.5%
        percentages = [10, 5]

        result = _compound_percentage_returns(percentages)

        self.assertAlmostEqual(result, 15.5, places=5)

    def test_simple_compounding_not_addition(self):
        """Verify compounding is used, not simple addition."""
        # If using addition: 10 + 10 = 20%
        # If using compounding: (1.1) * (1.1) - 1 = 0.21 = 21%
        percentages = [10, 10]

        result = _compound_percentage_returns(percentages)

        # Should be 21%, not 20%
        self.assertAlmostEqual(result, 21.0, places=5)

    def test_negative_returns(self):
        """Test compounding with negative returns."""
        # -10% followed by -10%
        # (1 - 0.10) * (1 - 0.10) - 1 = 0.81 - 1 = -0.19 = -19%
        percentages = [-10, -10]

        result = _compound_percentage_returns(percentages)

        self.assertAlmostEqual(result, -19.0, places=5)

    def test_mixed_positive_negative(self):
        """Test compounding with mixed positive and negative returns."""
        # +20% followed by -10%
        # (1 + 0.20) * (1 - 0.10) - 1 = 1.2 * 0.9 - 1 = 1.08 - 1 = 0.08 = 8%
        percentages = [20, -10]

        result = _compound_percentage_returns(percentages)

        self.assertAlmostEqual(result, 8.0, places=5)

    def test_ignores_none(self):
        """Test that None values are ignored."""
        percentages = [10, None, 10]

        result = _compound_percentage_returns(percentages)

        # Only 10% and 10%: 21%
        self.assertAlmostEqual(result, 21.0, places=5)

    def test_empty_list(self):
        """Test with empty list."""
        result = _compound_percentage_returns([])
        self.assertIsNone(result)

    def test_all_none(self):
        """Test when all values are None."""
        percentages = [None, None, None]
        result = _compound_percentage_returns(percentages)
        self.assertIsNone(result)

    def test_single_return(self):
        """Test with single return."""
        percentages = [15]

        result = _compound_percentage_returns(percentages)

        self.assertAlmostEqual(result, 15.0, places=5)

    def test_zero_returns(self):
        """Test with zero returns."""
        # 0% doesn't change the total
        percentages = [10, 0, 5]

        result = _compound_percentage_returns(percentages)

        # (1.1) * (1.0) * (1.05) - 1 = 1.155 - 1 = 15.5%
        self.assertAlmostEqual(result, 15.5, places=5)

    def test_large_loss_recovery(self):
        """Test recovery from large loss."""
        # -50% followed by +100% = back to even
        # (1 - 0.5) * (1 + 1.0) - 1 = 0.5 * 2 - 1 = 0%
        percentages = [-50, 100]

        result = _compound_percentage_returns(percentages)

        self.assertAlmostEqual(result, 0.0, places=5)


class TestGenerateBacktestSummaryMetrics(unittest.TestCase):
    """Tests for generate_backtest_summary_metrics function."""

    # ==========================================================
    # Edge Cases
    # ==========================================================

    def test_empty_list(self):
        """Test with empty list of metrics."""
        result = generate_backtest_summary_metrics([])

        # Should return empty BacktestSummaryMetrics
        self.assertIsNotNone(result)

    def test_all_none_metrics(self):
        """Test with list containing only None values."""
        result = generate_backtest_summary_metrics([None, None, None])

        self.assertIsNotNone(result)

    def test_single_metrics(self):
        """Test with single BacktestMetrics."""
        metrics = create_mock_backtest_metrics(
            total_net_gain=1000,
            number_of_trades=10,
            number_of_trades_closed=8,
        )

        result = generate_backtest_summary_metrics([metrics])

        self.assertEqual(result.total_net_gain, 1000)
        self.assertEqual(result.number_of_trades, 10)
        self.assertEqual(result.number_of_trades_closed, 8)

    # ==========================================================
    # Absolute Values (Summed)
    # ==========================================================

    def test_total_net_gain_summed(self):
        """Test that total_net_gain is summed across periods."""
        metrics1 = create_mock_backtest_metrics(total_net_gain=100)
        metrics2 = create_mock_backtest_metrics(total_net_gain=200)
        metrics3 = create_mock_backtest_metrics(total_net_gain=300)

        result = generate_backtest_summary_metrics([metrics1, metrics2, metrics3])

        # Should be summed: 100 + 200 + 300 = 600
        self.assertEqual(result.total_net_gain, 600)

    def test_total_growth_summed(self):
        """Test that total_growth is summed across periods."""
        metrics1 = create_mock_backtest_metrics(total_growth=500)
        metrics2 = create_mock_backtest_metrics(total_growth=300)

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        self.assertEqual(result.total_growth, 800)

    def test_number_of_trades_summed(self):
        """Test that number_of_trades is summed across periods."""
        metrics1 = create_mock_backtest_metrics(number_of_trades=10)
        metrics2 = create_mock_backtest_metrics(number_of_trades=15)

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        self.assertEqual(result.number_of_trades, 25)

    def test_number_of_trades_closed_summed(self):
        """Test that number_of_trades_closed is summed."""
        metrics1 = create_mock_backtest_metrics(number_of_trades_closed=8)
        metrics2 = create_mock_backtest_metrics(number_of_trades_closed=12)

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        self.assertEqual(result.number_of_trades_closed, 20)

    # ==========================================================
    # Percentage Returns (Compounded)
    # ==========================================================

    def test_percentage_returns_compounded(self):
        """Test that percentage returns are compounded, not summed."""
        # Period 1: 10%, Period 2: 10%
        # Compounded: (1.1 * 1.1) - 1 = 21%, NOT 20%
        metrics1 = create_mock_backtest_metrics(total_net_gain_percentage=10)
        metrics2 = create_mock_backtest_metrics(total_net_gain_percentage=10)

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        self.assertAlmostEqual(result.total_net_gain_percentage, 21.0, places=3)

    def test_growth_percentage_compounded(self):
        """Test that growth percentage is compounded."""
        metrics1 = create_mock_backtest_metrics(total_growth_percentage=20)
        metrics2 = create_mock_backtest_metrics(total_growth_percentage=10)

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        # (1.2 * 1.1) - 1 = 32%
        self.assertAlmostEqual(result.total_growth_percentage, 32.0, places=3)

    # ==========================================================
    # Risk-Adjusted Ratios (Weighted by Time)
    # ==========================================================

    def test_sharpe_ratio_weighted_by_time(self):
        """Test that Sharpe ratio is weighted by time period."""
        # Period 1: 365 days, Sharpe = 2.0
        # Period 2: 365 days, Sharpe = 1.0
        # Weighted average: (2.0 * 365 + 1.0 * 365) / (365 + 365) = 1.5
        metrics1 = create_mock_backtest_metrics(
            sharpe_ratio=2.0, total_number_of_days=365
        )
        metrics2 = create_mock_backtest_metrics(
            sharpe_ratio=1.0, total_number_of_days=365
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        self.assertAlmostEqual(result.sharpe_ratio, 1.5, places=5)

    def test_sharpe_ratio_weighted_unequal_periods(self):
        """Test Sharpe weighted with unequal time periods."""
        # Period 1: 100 days, Sharpe = 3.0
        # Period 2: 300 days, Sharpe = 1.0
        # Weighted: (3.0 * 100 + 1.0 * 300) / 400 = 600 / 400 = 1.5
        metrics1 = create_mock_backtest_metrics(
            sharpe_ratio=3.0, total_number_of_days=100
        )
        metrics2 = create_mock_backtest_metrics(
            sharpe_ratio=1.0, total_number_of_days=300
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        self.assertAlmostEqual(result.sharpe_ratio, 1.5, places=5)

    def test_cagr_weighted_by_time(self):
        """Test that CAGR is weighted by time period."""
        metrics1 = create_mock_backtest_metrics(
            cagr=0.20, total_number_of_days=365
        )
        metrics2 = create_mock_backtest_metrics(
            cagr=0.10, total_number_of_days=365
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        # Equal weights: (0.20 + 0.10) / 2 = 0.15
        self.assertAlmostEqual(result.cagr, 0.15, places=5)

    def test_sortino_ratio_weighted_by_time(self):
        """Test that Sortino ratio is weighted by time."""
        metrics1 = create_mock_backtest_metrics(
            sortino_ratio=2.5, total_number_of_days=200
        )
        metrics2 = create_mock_backtest_metrics(
            sortino_ratio=1.5, total_number_of_days=200
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        self.assertAlmostEqual(result.sortino_ratio, 2.0, places=5)

    # ==========================================================
    # Max Drawdown (Worst Value)
    # ==========================================================

    def test_max_drawdown_takes_minimum(self):
        """Test that max drawdown takes the worst (minimum) value."""
        # Drawdowns are negative, so -30% is worse than -10%
        metrics1 = create_mock_backtest_metrics(max_drawdown=-0.10)
        metrics2 = create_mock_backtest_metrics(max_drawdown=-0.30)
        metrics3 = create_mock_backtest_metrics(max_drawdown=-0.15)

        result = generate_backtest_summary_metrics([metrics1, metrics2, metrics3])

        # Should be the worst (most negative): -30%
        self.assertEqual(result.max_drawdown, -0.30)

    def test_max_drawdown_duration_takes_maximum(self):
        """Test that max drawdown duration takes the longest."""
        metrics1 = create_mock_backtest_metrics(max_drawdown_duration=30)
        metrics2 = create_mock_backtest_metrics(max_drawdown_duration=60)
        metrics3 = create_mock_backtest_metrics(max_drawdown_duration=45)

        result = generate_backtest_summary_metrics([metrics1, metrics2, metrics3])

        # Should be the longest: 60 days
        self.assertEqual(result.max_drawdown_duration, 60)

    # ==========================================================
    # Win Rate (Weighted by Trade Count)
    # ==========================================================

    def test_win_rate_weighted_by_trade_count(self):
        """Test that win rate is weighted by number of closed trades."""
        # Period 1: 10 trades, 80% win rate
        # Period 2: 30 trades, 60% win rate
        # Weighted: (80 * 10 + 60 * 30) / (10 + 30) = 2600 / 40 = 65%
        metrics1 = create_mock_backtest_metrics(
            win_rate=80.0, number_of_trades_closed=10
        )
        metrics2 = create_mock_backtest_metrics(
            win_rate=60.0, number_of_trades_closed=30
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        self.assertAlmostEqual(result.win_rate, 65.0, places=5)

    def test_win_loss_ratio_weighted_by_trade_count(self):
        """Test that win/loss ratio is weighted by trade count."""
        metrics1 = create_mock_backtest_metrics(
            win_loss_ratio=2.0, number_of_trades_closed=10
        )
        metrics2 = create_mock_backtest_metrics(
            win_loss_ratio=1.0, number_of_trades_closed=10
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        # Equal trade counts: (2.0 + 1.0) / 2 = 1.5
        self.assertAlmostEqual(result.win_loss_ratio, 1.5, places=5)

    # ==========================================================
    # Profit Factor (Recalculated from Totals)
    # ==========================================================

    def test_profit_factor_recalculated(self):
        """Test that profit factor is recalculated from gross profit/loss."""
        # Period 1: gross_profit=300, gross_loss=-100
        # Period 2: gross_profit=200, gross_loss=-50
        # Total: gross_profit=500, gross_loss=150
        # Profit factor = 500 / 150 = 3.33
        metrics1 = create_mock_backtest_metrics(
            gross_profit=300, gross_loss=-100
        )
        metrics2 = create_mock_backtest_metrics(
            gross_profit=200, gross_loss=-50
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        self.assertAlmostEqual(result.profit_factor, 500 / 150, places=3)

    def test_profit_factor_with_no_losses(self):
        """Test profit factor when there are no losses."""
        metrics1 = create_mock_backtest_metrics(
            gross_profit=300, gross_loss=0, profit_factor=float('inf')
        )
        metrics2 = create_mock_backtest_metrics(
            gross_profit=200, gross_loss=0, profit_factor=float('inf')
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        # Should fallback to weighted average (may be inf or None)
        self.assertIsNotNone(result.profit_factor)

    # ==========================================================
    # Average Trade Metrics (Weighted by Appropriate Count)
    # ==========================================================

    def test_average_trade_return_weighted_by_trades(self):
        """Test average trade return weighted by closed trades."""
        metrics1 = create_mock_backtest_metrics(
            average_trade_return=100, number_of_trades_closed=20
        )
        metrics2 = create_mock_backtest_metrics(
            average_trade_return=50, number_of_trades_closed=20
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        # Equal weights: (100 + 50) / 2 = 75
        self.assertAlmostEqual(result.average_trade_return, 75.0, places=5)

    # ==========================================================
    # Integration Tests - Realistic Scenarios
    # ==========================================================

    def test_two_equal_periods(self):
        """Test combining two equal-length periods."""
        metrics1 = create_mock_backtest_metrics(
            total_net_gain=1000,
            total_net_gain_percentage=10,
            sharpe_ratio=1.5,
            max_drawdown=-0.15,
            number_of_trades=20,
            number_of_trades_closed=18,
            win_rate=60,
            total_number_of_days=365,
        )
        metrics2 = create_mock_backtest_metrics(
            total_net_gain=500,
            total_net_gain_percentage=5,
            sharpe_ratio=1.0,
            max_drawdown=-0.10,
            number_of_trades=10,
            number_of_trades_closed=8,
            win_rate=50,
            total_number_of_days=365,
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        # Verify summed values
        self.assertEqual(result.total_net_gain, 1500)
        self.assertEqual(result.number_of_trades, 30)
        self.assertEqual(result.number_of_trades_closed, 26)

        # Verify compounded percentage
        # (1.10 * 1.05) - 1 = 15.5%
        self.assertAlmostEqual(result.total_net_gain_percentage, 15.5, places=3)

        # Verify weighted Sharpe (equal time weights)
        self.assertAlmostEqual(result.sharpe_ratio, 1.25, places=5)

        # Verify worst drawdown
        self.assertEqual(result.max_drawdown, -0.15)

        # Verify win rate weighted by trades
        # (60 * 18 + 50 * 8) / 26 = 1480 / 26 ≈ 56.92%
        expected_win_rate = (60 * 18 + 50 * 8) / 26
        self.assertAlmostEqual(result.win_rate, expected_win_rate, places=3)

    def test_three_periods_different_lengths(self):
        """Test combining three periods of different lengths."""
        metrics1 = create_mock_backtest_metrics(
            sharpe_ratio=2.0,
            total_number_of_days=100,
        )
        metrics2 = create_mock_backtest_metrics(
            sharpe_ratio=1.5,
            total_number_of_days=200,
        )
        metrics3 = create_mock_backtest_metrics(
            sharpe_ratio=1.0,
            total_number_of_days=100,
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2, metrics3])

        # Weighted: (2.0*100 + 1.5*200 + 1.0*100) / 400 = 600/400 = 1.5
        self.assertAlmostEqual(result.sharpe_ratio, 1.5, places=5)


class TestGenerateBacktestSummaryMetricsCalculationValidity(unittest.TestCase):
    """
    Tests to verify that the aggregation calculations make financial sense.
    """

    def test_compounding_makes_sense_for_returns(self):
        """
        Verify that compounding is mathematically correct for returns.

        Example: Start with $1000
        - Period 1: +10% -> $1100
        - Period 2: +10% -> $1210
        Total return: ($1210 - $1000) / $1000 = 21%, NOT 20%
        """
        metrics1 = create_mock_backtest_metrics(total_net_gain_percentage=10)
        metrics2 = create_mock_backtest_metrics(total_net_gain_percentage=10)

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        # Compound return should be 21%
        self.assertAlmostEqual(result.total_net_gain_percentage, 21.0, places=3)

    def test_weighted_average_makes_sense_for_ratios(self):
        """
        Verify that weighted averaging by time makes sense for ratios.

        A strategy with Sharpe 2.0 over 300 days should count more
        than one with Sharpe 1.0 over 100 days.
        """
        # Better strategy for longer period
        metrics1 = create_mock_backtest_metrics(
            sharpe_ratio=2.0, total_number_of_days=300
        )
        # Worse strategy for shorter period
        metrics2 = create_mock_backtest_metrics(
            sharpe_ratio=1.0, total_number_of_days=100
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        # (2.0*300 + 1.0*100) / 400 = 700/400 = 1.75
        # Should be closer to 2.0 than to 1.0
        self.assertAlmostEqual(result.sharpe_ratio, 1.75, places=5)
        self.assertGreater(result.sharpe_ratio, 1.5)

    def test_max_drawdown_worst_case_makes_sense(self):
        """
        Verify that taking worst drawdown makes financial sense.

        If one period had -30% drawdown and another had -10%,
        the combined worst case is -30%, not an average.
        """
        metrics1 = create_mock_backtest_metrics(max_drawdown=-0.30)
        metrics2 = create_mock_backtest_metrics(max_drawdown=-0.10)

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        # Should be the worst case
        self.assertEqual(result.max_drawdown, -0.30)

    def test_win_rate_weighted_by_trades_makes_sense(self):
        """
        Verify that win rate weighted by trades makes financial sense.

        Example:
        - Period 1: 10 trades, 90% win rate (9 wins)
        - Period 2: 90 trades, 50% win rate (45 wins)
        - Combined: 54 wins out of 100 trades = 54% win rate

        NOT: (90 + 50) / 2 = 70% (simple average)
        """
        metrics1 = create_mock_backtest_metrics(
            win_rate=90, number_of_trades_closed=10
        )
        metrics2 = create_mock_backtest_metrics(
            win_rate=50, number_of_trades_closed=90
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        # Weighted: (90*10 + 50*90) / 100 = 5400 / 100 = 54%
        self.assertAlmostEqual(result.win_rate, 54.0, places=3)

    def test_profit_factor_from_totals_makes_sense(self):
        """
        Verify that profit factor calculated from totals is correct.

        profit_factor = total_gross_profit / total_gross_loss
        NOT weighted average of individual profit factors
        """
        # Period 1: profit=200, loss=100, PF=2.0
        # Period 2: profit=100, loss=100, PF=1.0
        # Simple avg of PF: (2.0 + 1.0) / 2 = 1.5 (WRONG)
        # From totals: 300 / 200 = 1.5 (happens to match in this case)

        # Better example:
        # Period 1: profit=400, loss=100, PF=4.0
        # Period 2: profit=100, loss=100, PF=1.0
        # Simple avg: (4.0 + 1.0) / 2 = 2.5 (WRONG)
        # From totals: 500 / 200 = 2.5 (happens to match here too)

        # Even better example:
        # Period 1: profit=300, loss=100, PF=3.0
        # Period 2: profit=200, loss=200, PF=1.0
        # Simple avg: (3.0 + 1.0) / 2 = 2.0 (WRONG)
        # From totals: 500 / 300 = 1.67 (CORRECT)
        metrics1 = create_mock_backtest_metrics(
            gross_profit=300, gross_loss=-100
        )
        metrics2 = create_mock_backtest_metrics(
            gross_profit=200, gross_loss=-200
        )

        result = generate_backtest_summary_metrics([metrics1, metrics2])

        # From totals: 500 / 300 = 1.67
        expected_pf = 500 / 300
        self.assertAlmostEqual(result.profit_factor, expected_pf, places=3)


if __name__ == "__main__":
    unittest.main()

