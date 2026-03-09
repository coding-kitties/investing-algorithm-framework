import unittest
from datetime import datetime, date

from investing_algorithm_framework.analysis.ranking import create_weights, \
    combine_backtest_metrics, rank_results, normalize, compute_score
from investing_algorithm_framework.domain import BacktestEvaluationFocus, \
    Trade, BacktestMetrics, Backtest, \
    BacktestSummaryMetrics, OperationalException


class TestCreateWeights(unittest.TestCase):
    """Tests for the create_weights function."""

    def test_default_returns_balanced_weights(self):
        """Test that no arguments returns BALANCED weights."""
        weights = create_weights()
        expected = BacktestEvaluationFocus.BALANCED.get_weights()
        self.assertEqual(weights, expected)

    def test_none_focus_returns_balanced_weights(self):
        """Test that focus=None returns BALANCED weights."""
        weights = create_weights(focus=None)
        expected = BacktestEvaluationFocus.BALANCED.get_weights()
        self.assertEqual(weights, expected)

    def test_balanced_focus(self):
        """Test BALANCED focus returns correct weights."""
        weights = create_weights(focus=BacktestEvaluationFocus.BALANCED)
        expected = BacktestEvaluationFocus.BALANCED.get_weights()
        self.assertEqual(weights, expected)

    def test_profit_focus(self):
        """Test PROFIT focus returns correct weights."""
        weights = create_weights(focus=BacktestEvaluationFocus.PROFIT)
        expected = BacktestEvaluationFocus.PROFIT.get_weights()
        self.assertEqual(weights, expected)

    def test_frequency_focus(self):
        """Test FREQUENCY focus returns correct weights."""
        weights = create_weights(focus=BacktestEvaluationFocus.FREQUENCY)
        expected = BacktestEvaluationFocus.FREQUENCY.get_weights()
        self.assertEqual(weights, expected)

    def test_risk_adjusted_focus(self):
        """Test RISK_ADJUSTED focus returns correct weights."""
        weights = create_weights(focus=BacktestEvaluationFocus.RISK_ADJUSTED)
        expected = BacktestEvaluationFocus.RISK_ADJUSTED.get_weights()
        self.assertEqual(weights, expected)

    def test_custom_weights_override_defaults(self):
        """Test that custom_weights override default values."""
        custom = {"sharpe_ratio": 10.0, "win_rate": 5.0}
        weights = create_weights(custom_weights=custom)

        self.assertEqual(weights["sharpe_ratio"], 10.0)
        self.assertEqual(weights["win_rate"], 5.0)

    def test_custom_weights_merge_with_focus(self):
        """Test that custom_weights merge with focus weights."""
        custom = {"sharpe_ratio": 99.0}
        weights = create_weights(
            focus=BacktestEvaluationFocus.BALANCED,
            custom_weights=custom
        )

        # Custom value should override
        self.assertEqual(weights["sharpe_ratio"], 99.0)

        # Other balanced weights should still be present
        balanced_weights = BacktestEvaluationFocus.BALANCED.get_weights()
        for key in balanced_weights:
            if key != "sharpe_ratio":
                self.assertEqual(weights[key], balanced_weights[key])

    def test_custom_weights_add_new_metrics(self):
        """Test that custom_weights can add new metrics not in focus."""
        custom = {"new_custom_metric": 7.5}
        weights = create_weights(custom_weights=custom)

        self.assertEqual(weights["new_custom_metric"], 7.5)

    def test_custom_weights_with_profit_focus(self):
        """Test custom_weights combined with PROFIT focus."""
        custom = {"total_net_gain_percentage": 100.0}
        weights = create_weights(
            focus=BacktestEvaluationFocus.PROFIT,
            custom_weights=custom
        )

        self.assertEqual(weights["total_net_gain_percentage"], 100.0)

    def test_returns_dict_type(self):
        """Test that create_weights always returns a dict."""
        result = create_weights()
        self.assertIsInstance(result, dict)

        result = create_weights(focus=BacktestEvaluationFocus.PROFIT)
        self.assertIsInstance(result, dict)

        result = create_weights(custom_weights={"test": 1.0})
        self.assertIsInstance(result, dict)

    def test_weights_are_numeric(self):
        """Test that all weight values are numeric."""
        for focus in BacktestEvaluationFocus:
            weights = create_weights(focus=focus)
            for key, value in weights.items():
                self.assertIsInstance(
                    value, (int, float),
                    f"Weight for {key} should be numeric, got {type(value)}"
                )

    def test_empty_custom_weights(self):
        """Test that empty custom_weights dict doesn't affect result."""
        weights_no_custom = create_weights()
        weights_empty_custom = create_weights(custom_weights={})

        self.assertEqual(weights_no_custom, weights_empty_custom)

    def test_custom_weights_none_is_same_as_no_custom(self):
        """Test that custom_weights=None gives same result as omitting it."""
        weights_default = create_weights()
        weights_none = create_weights(custom_weights=None)

        self.assertEqual(weights_default, weights_none)


class TestCombineMetrics(unittest.TestCase):

    def test_combine_metrics(self):

        # Variation 1
        backtest_metrics_1 = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            equity_curve=[
                (1.0, datetime(2020, 1, 1)),
                (1.5, datetime(2020, 6, 30)),
                (2.0, datetime(2020, 12, 31)),
            ],
            total_growth=1000.0,
            total_growth_percentage=100.0,
            total_net_gain=1000.0,
            total_net_gain_percentage=100.0,
            final_value=2000.0,
            cagr=0.15,
            sharpe_ratio=1.2,
            rolling_sharpe_ratio=[(0.5, datetime(2020, 6, 30)),
                                  (1.2, datetime(2020, 12, 31))],
            sortino_ratio=1.0,
            calmar_ratio=0.8,
            profit_factor=1.5,
            gross_profit=1500.0,
            gross_loss=500.0,
            annual_volatility=0.2,
            monthly_returns=[
                (0.05, datetime(2020, m, 1)) for m in range(1, 13)
            ],
            yearly_returns=[(1.0, date(2020, 12, 31))],
            drawdown_series=[(0.1, datetime(2020, 6, 30))],
            max_drawdown=0.2,
            max_drawdown_absolute=400.0,
            max_daily_drawdown=0.05,
            max_drawdown_duration=30,
            trades_per_year=50,
            trade_per_day=0.2,
            exposure_ratio=0.75,
            average_trade_gain=200,
            average_trade_gain_percentage=0.1,
            average_trade_loss=100,
            average_trade_loss_percentage=0.1,
            best_trade=Trade(id=1, open_price=100,
                             opened_at=datetime(2020, 1, 1),
                             closed_at=datetime(2020, 2, 1), orders=[],
                             target_symbol="BTC",
                             trading_symbol="EUR", amount=1, cost=100,
                             available_amount=1,
                             remaining=0, filled_amount=1, status="closed"),
            worst_trade=Trade(id=2, open_price=100,
                              opened_at=datetime(2020, 3, 1),
                              closed_at=datetime(2020, 4, 1), orders=[],
                              target_symbol="BTC",
                              trading_symbol="EUR", amount=1, cost=100,
                              available_amount=1,
                              remaining=0, filled_amount=1, status="closed"),
            average_trade_duration=2.5,
            number_of_trades=50,
            win_rate=0.55,
            win_loss_ratio=1.2,
            percentage_winning_months=60.0,
            percentage_winning_years=100.0,
            average_monthly_return=0.04,
            average_monthly_return_losing_months=-0.02,
            average_monthly_return_winning_months=0.08,
            best_month=(0.12, datetime(2020, 8, 1)),
            best_year=(1.0, date(2020, 12, 31)),
            worst_month=(-0.05, datetime(2020, 3, 1)),
            worst_year=(0.2, date(2020, 12, 31)),
        )

        # Variation 2
        backtest_metrics_2 = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            equity_curve=[
                (1.0, datetime(2020, 1, 1)),
                (1.2, datetime(2020, 6, 30)),
                (1.4, datetime(2020, 12, 31)),
            ],
            total_growth=400.0,
            total_growth_percentage=40.0,
            total_net_gain=400.0,
            total_net_gain_percentage=40.0,
            final_value=1400.0,
            cagr=0.08,
            sharpe_ratio=0.6,
            rolling_sharpe_ratio=[(0.3, datetime(2020, 6, 30)),
                                  (0.6, datetime(2020, 12, 31))],
            sortino_ratio=0.5,
            calmar_ratio=0.4,
            profit_factor=1.2,
            gross_profit=1000.0,
            gross_loss=600.0,
            annual_volatility=0.15,
            monthly_returns=[
                (0.02, datetime(2020, m, 1)) for m in range(1, 13)
            ],
            yearly_returns=[(0.4, date(2020, 12, 31))],
            drawdown_series=[(0.15, datetime(2020, 7, 31))],
            max_drawdown=0.25,
            max_drawdown_absolute=350.0,
            max_daily_drawdown=0.06,
            max_drawdown_duration=40,
            trades_per_year=30,
            trade_per_day=0.12,
            exposure_ratio=0.6,
            average_trade_gain_percentage=0.07,
            average_trade_gain=140.0,
            average_trade_loss=-80.0,
            average_trade_loss_percentage=-0.04,
            best_trade=Trade(id=3, open_price=120,
                             opened_at=datetime(2020, 5, 1),
                             closed_at=datetime(2020, 6, 1), orders=[],
                             target_symbol="BTC",
                             trading_symbol="EUR", amount=1, cost=120,
                             available_amount=1,
                             remaining=0, filled_amount=1, status="closed"),
            worst_trade=Trade(id=4, open_price=100,
                              opened_at=datetime(2020, 7, 1),
                              closed_at=datetime(2020, 8, 1), orders=[],
                              target_symbol="BTC",
                              trading_symbol="EUR", amount=1, cost=100,
                              available_amount=1,
                              remaining=0, filled_amount=1, status="closed"),
            average_trade_duration=3.2,
            number_of_trades=30,
            win_rate=0.45,
            win_loss_ratio=0.9,
            percentage_winning_months=50.0,
            percentage_winning_years=100.0,
            average_monthly_return=0.025,
            average_monthly_return_losing_months=-0.03,
            average_monthly_return_winning_months=0.06,
            best_month=(0.08, datetime(2020, 10, 1)),
            best_year=(0.4, date(2020, 12, 31)),
            worst_month=(-0.06, datetime(2020, 4, 1)),
            worst_year=(0.1, date(2020, 12, 31)),
        )

        combined = combine_backtest_metrics(
            [backtest_metrics_1, backtest_metrics_2]
        )

        self.assertEqual(700, combined.total_net_gain)
        self.assertAlmostEqual(70.0, combined.total_net_gain_percentage)
        self.assertAlmostEqual(70.0, combined.total_growth_percentage)
        self.assertEqual(700.0, combined.total_growth)
        self.assertEqual(0.5, combined.win_rate)

    def test_combine_single_metrics(self):
        """Combining a single metrics object should return it unchanged."""
        metrics = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            total_net_gain=500.0,
            total_net_gain_percentage=50.0,
            win_rate=0.6,
        )
        combined = combine_backtest_metrics([metrics])
        self.assertEqual(500.0, combined.total_net_gain)
        self.assertEqual(0.6, combined.win_rate)

    def test_combine_empty_raises(self):
        """Combining an empty list should raise OperationalException."""
        with self.assertRaises(OperationalException):
            combine_backtest_metrics([])

    def test_combine_max_drawdown_takes_worst(self):
        """Max drawdown should be the worst (maximum) across all metrics."""
        m1 = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            max_drawdown=0.10,
        )
        m2 = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            max_drawdown=0.30,
        )
        combined = combine_backtest_metrics([m1, m2])
        self.assertEqual(0.30, combined.max_drawdown)

    def test_combine_number_of_trades_summed(self):
        """Number of trades should be summed, not averaged."""
        m1 = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            number_of_trades=20,
        )
        m2 = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            number_of_trades=30,
        )
        combined = combine_backtest_metrics([m1, m2])
        self.assertEqual(50, combined.number_of_trades)

    def test_combine_date_range_spans_all(self):
        """Combined date range should span all input date ranges."""
        m1 = BacktestMetrics(
            backtest_start_date=datetime(2020, 3, 1),
            backtest_end_date=datetime(2020, 9, 30),
        )
        m2 = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
        )
        combined = combine_backtest_metrics([m1, m2])
        self.assertEqual(datetime(2020, 1, 1), combined.backtest_start_date)
        self.assertEqual(datetime(2020, 12, 31), combined.backtest_end_date)


class TestNormalize(unittest.TestCase):
    """Tests for the normalize helper function."""

    def test_midpoint(self):
        self.assertAlmostEqual(0.5, normalize(50, 0, 100))

    def test_min_value(self):
        self.assertAlmostEqual(0.0, normalize(0, 0, 100))

    def test_max_value(self):
        self.assertAlmostEqual(1.0, normalize(100, 0, 100))

    def test_equal_min_max_returns_zero(self):
        self.assertEqual(0, normalize(5, 5, 5))

    def test_none_returns_zero(self):
        self.assertEqual(0, normalize(None, 0, 100))

    def test_nan_returns_zero(self):
        self.assertEqual(0, normalize(float('nan'), 0, 100))

    def test_inf_returns_zero(self):
        self.assertEqual(0, normalize(float('inf'), 0, 100))

    def test_negative_range(self):
        self.assertAlmostEqual(0.5, normalize(0, -100, 100))


class TestComputeScore(unittest.TestCase):
    """Tests for the compute_score function."""

    def test_basic_score(self):
        """Score should be weighted sum of normalized values."""
        metrics = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            sharpe_ratio=1.5,
            win_rate=0.6,
        )
        weights = {"sharpe_ratio": 2.0, "win_rate": 1.0}
        ranges = {"sharpe_ratio": (0, 3.0), "win_rate": (0, 1.0)}
        score = compute_score(metrics, weights, ranges)
        # normalized sharpe = 1.5/3 = 0.5 → 2.0 * 0.5 = 1.0
        # normalized win_rate = 0.6/1 = 0.6 → 1.0 * 0.6 = 0.6
        self.assertAlmostEqual(1.6, score)

    def test_missing_attribute_is_skipped(self):
        """Attributes not on the metrics object should be skipped."""
        metrics = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            sharpe_ratio=1.0,
        )
        weights = {"sharpe_ratio": 1.0, "nonexistent_metric": 5.0}
        ranges = {"sharpe_ratio": (0, 2.0)}
        score = compute_score(metrics, weights, ranges)
        self.assertAlmostEqual(0.5, score)

    def test_empty_weights_returns_zero(self):
        metrics = BacktestMetrics(
            backtest_start_date=datetime(2020, 1, 1),
            backtest_end_date=datetime(2020, 12, 31),
            sharpe_ratio=1.5,
        )
        score = compute_score(metrics, {}, {})
        self.assertEqual(0, score)


class TestRankResults(unittest.TestCase):
    """Tests for the rank_results function."""

    @staticmethod
    def _make_backtest(algorithm_id, sharpe, win_rate, net_gain_pct):
        """Helper to create a Backtest with summary metrics."""
        summary = BacktestSummaryMetrics(
            sharpe_ratio=sharpe,
            win_rate=win_rate,
            total_net_gain_percentage=net_gain_pct,
        )
        return Backtest(
            algorithm_id=algorithm_id,
            backtest_summary=summary,
        )

    def test_ranking_order(self):
        """Higher scoring backtests should appear first."""
        bt_good = self._make_backtest("good", 2.0, 0.8, 50.0)
        bt_mid = self._make_backtest("mid", 1.0, 0.5, 20.0)
        bt_bad = self._make_backtest("bad", 0.2, 0.3, 5.0)

        ranked = rank_results([bt_bad, bt_good, bt_mid])
        ids = [bt.algorithm_id for bt in ranked]
        self.assertEqual("good", ids[0])
        self.assertEqual("bad", ids[-1])

    def test_ranking_returns_all_backtests(self):
        """All input backtests should appear in the output."""
        backtests = [
            self._make_backtest(f"alg_{i}", i * 0.5, i * 0.1, i * 10)
            for i in range(5)
        ]
        ranked = rank_results(backtests)
        self.assertEqual(len(backtests), len(ranked))

    def test_ranking_with_custom_weights(self):
        """Custom weights should change the ranking order."""
        bt_high_sharpe = self._make_backtest("sharpe", 3.0, 0.3, 10.0)
        bt_high_win = self._make_backtest("win", 0.5, 0.9, 10.0)

        # Default balanced weights: sharpe matters
        ranked_default = rank_results([bt_high_sharpe, bt_high_win])
        # Win-rate-only weights: win_rate matters
        ranked_win = rank_results(
            [bt_high_sharpe, bt_high_win],
            weights={"win_rate": 10.0}
        )
        self.assertEqual("win", ranked_win[0].algorithm_id)

    def test_ranking_with_callable_filter(self):
        """Callable filter should exclude backtests that don't pass."""
        bt_good = self._make_backtest("good", 2.0, 0.8, 50.0)
        bt_bad = self._make_backtest("bad", 0.2, 0.3, -5.0)

        ranked = rank_results(
            [bt_good, bt_bad],
            filter_fn=lambda m: m.total_net_gain_percentage > 0
        )
        self.assertEqual(1, len(ranked))
        self.assertEqual("good", ranked[0].algorithm_id)

    def test_ranking_with_dict_filter(self):
        """Dict filter should exclude backtests where conditions fail."""
        bt_good = self._make_backtest("good", 2.0, 0.8, 50.0)
        bt_bad = self._make_backtest("bad", 0.2, 0.3, 5.0)

        ranked = rank_results(
            [bt_good, bt_bad],
            filter_fn={"win_rate": lambda v: v is not None and v > 0.5}
        )
        self.assertEqual(1, len(ranked))
        self.assertEqual("good", ranked[0].algorithm_id)

    def test_ranking_empty_list(self):
        """Ranking an empty list should return an empty list."""
        ranked = rank_results([])
        self.assertEqual(0, len(ranked))

    def test_ranking_with_no_summary(self):
        """Backtests with no summary should be excluded from ranking."""
        bt_with = self._make_backtest("with", 2.0, 0.8, 50.0)
        bt_without = Backtest(
            algorithm_id="without",
            backtest_summary=None,
        )
        ranked = rank_results([bt_with, bt_without])
        self.assertEqual(1, len(ranked))
        self.assertEqual("with", ranked[0].algorithm_id)


if __name__ == "__main__":
    unittest.main()
