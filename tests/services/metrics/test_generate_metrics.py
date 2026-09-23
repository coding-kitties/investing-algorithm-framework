import os
from unittest import TestCase

from investing_algorithm_framework import (
    BacktestMetrics,
    BacktestRun,
    create_backtest_metrics,
)
from investing_algorithm_framework.services.metrics.trades import (
    get_directional_trade_statistics,
)

class TestGenerateMetrics(TestCase):
    def test_resampling_is_shared_and_does_not_mutate_cached_frame(self):
        from investing_algorithm_framework.services.metrics.inputs import (
            prepare_metric_inputs,
        )
        from investing_algorithm_framework.services.metrics._returns_helper \
            import snapshots_to_dataframe, daily_twr_returns
        from investing_algorithm_framework.services.metrics.returns import (
            get_monthly_returns, get_yearly_returns,
        )

        run = BacktestRun.open(os.path.join(
            self.backtest_run_directory, 'backtest_run_one'))
        snapshots = prepare_metric_inputs(run).portfolio_snapshots
        frame = snapshots_to_dataframe(snapshots)
        before = frame.copy()
        for function in (get_monthly_returns, get_yearly_returns,
                         daily_twr_returns, snapshots_to_dataframe):
            self.assertIs(function(snapshots), function(snapshots))
        self.assertTrue(frame.equals(before))
        self.assertEqual(frame.index.tz, before.index.tz)
        other = prepare_metric_inputs(run).portfolio_snapshots
        self.assertIsNot(snapshots_to_dataframe(other), frame)

    def test_compact_inputs_decode_histories_once_with_exact_metric_parity(self):
        import json
        from collections import Counter
        from unittest.mock import patch
        from investing_algorithm_framework import BacktestHistory
        from investing_algorithm_framework.services.metrics import generate

        run = BacktestRun.open(os.path.join(
            self.backtest_run_directory, 'backtest_run_one'))
        with patch.object(generate, 'prepare_metric_inputs', lambda run: run):
            expected = create_backtest_metrics(run, 0.024)
        counts = Counter()
        original = BacktestHistory.__iter__

        def tracked(history):
            if history is run.trades or history is run.portfolio_snapshots:
                counts[id(history)] += 1
            yield from original(history)

        with patch.object(BacktestHistory, '__iter__', tracked):
            actual = create_backtest_metrics(run, 0.024)
        self.assertEqual(counts[id(run.trades)], 1)
        self.assertEqual(counts[id(run.portfolio_snapshots)], 1)
        self.assertEqual(json.dumps(actual.to_dict(), sort_keys=True),
                         json.dumps(expected.to_dict(), sort_keys=True))

    def test_shared_trade_scan_matches_independent_helpers(self):
        from investing_algorithm_framework.services.metrics import trades
        from investing_algorithm_framework.services.metrics import profit_factor
        from investing_algorithm_framework.services.metrics import win_rate

        run = BacktestRun.open(os.path.join(
            self.backtest_run_directory, 'backtest_run_one'))
        functions = {
            'average_trade_duration': trades.get_average_trade_duration,
            'average_trade_size': trades.get_average_trade_size,
            'number_of_trades': trades.get_number_of_trades,
            'number_of_trades_closed': trades.get_number_of_closed_trades,
            'number_of_trades_opened': trades.get_number_of_open_trades,
            'gross_profit': profit_factor.get_gross_profit,
            'gross_loss': profit_factor.get_gross_loss,
            'profit_factor': profit_factor.get_profit_factor,
            'win_rate': win_rate.get_win_rate,
            'current_win_rate': win_rate.get_current_win_rate,
        }
        for history in (run.trades, run.trades[:0]):
            summary = trades.summarize_trade_history(iter(history), functions)
            for name, function in functions.items():
                self.assertEqual(summary[name], function(history), name)
            for name, value in trades.get_directional_trade_statistics(
                    history).items():
                self.assertEqual(summary[name], value, name)
            positive, percentage = trades.get_positive_trades(history)
            self.assertEqual(summary['number_of_positive_trades'], positive)
            self.assertEqual(summary['percentage_positive_trades'], percentage)
            negative, percentage = trades.get_negative_trades(history)
            self.assertEqual(summary['number_of_negative_trades'], negative)
            self.assertEqual(summary['percentage_negative_trades'], percentage)
    def setUp(self):
        # Must point to /tests/resources
        self.resource_directory = os.path.abspath(
            os.path.join(os.path.dirname(__file__), '..', '..', 'resources')
        )
        self.test_data_directory = os.path.join(
            self.resource_directory, 'test_data'
        )
        self.backtest_run_directory = os.path.join(
            self.test_data_directory, 'backtest_runs'
        )

    def test_generate_metrics(self):
        backtest_run = BacktestRun.open(
            os.path.join(self.backtest_run_directory, 'backtest_run_one')
        )
        backtest_metrics = create_backtest_metrics(
            backtest_run, risk_free_rate=0.024
        )
        self.assertIs(
            backtest_metrics.backtest_window,
            backtest_run.backtest_window,
        )
        self.assertEqual(
            backtest_metrics.backtest_start_date,
            backtest_run.backtest_start_date,
        )
        self.assertEqual(
            backtest_metrics.backtest_end_date,
            backtest_run.backtest_end_date,
        )
        self.assertIsInstance(
            backtest_metrics.number_of_positive_trades, int
        )
        self.assertIsInstance(
            backtest_metrics.number_of_negative_trades, int
        )
        self.assertIsInstance(
            backtest_metrics.percentage_positive_trades, float
        )
        self.assertIsInstance(
            backtest_metrics.percentage_negative_trades, float
        )
        directional = get_directional_trade_statistics(backtest_run.trades)
        self.assertEqual(
            backtest_metrics.number_of_long_trades,
            directional["number_of_long_trades"],
        )
        self.assertEqual(
            backtest_metrics.long_win_rate,
            directional["long_win_rate"],
        )
        self.assertEqual(
            backtest_metrics.number_of_short_trades,
            directional["number_of_short_trades"],
        )
        self.assertEqual(
            backtest_metrics.short_win_rate,
            directional["short_win_rate"],
        )
        restored = BacktestMetrics.from_dict(backtest_metrics.to_dict())
        self.assertEqual(
            restored.number_of_long_trades,
            backtest_metrics.number_of_long_trades,
        )
        self.assertEqual(
            restored.long_win_rate,
            backtest_metrics.long_win_rate,
        )
        self.assertEqual(
            restored.number_of_short_trades,
            backtest_metrics.number_of_short_trades,
        )
        self.assertEqual(
            restored.short_win_rate,
            backtest_metrics.short_win_rate,
        )

    def test_total_loss_is_gross_loss_magnitude(self):
        """Regression test for issue #511 (B1).

        Per-run ``BacktestMetrics.total_loss`` must equal the gross
        loss magnitude (``sum(abs(net_gain))`` over losing trades),
        not the snapshot net-return clamped at zero. In particular,
        ``total_loss`` must equal the ``gross_loss`` field, and
        ``total_loss_percentage`` must be ``total_loss /
        initial_unallocated`` (a non-negative decimal).
        """
        backtest_run = BacktestRun.open(
            os.path.join(self.backtest_run_directory, 'backtest_run_one')
        )
        metrics = create_backtest_metrics(
            backtest_run, risk_free_rate=0.024
        )

        # total_loss is a non-negative magnitude.
        self.assertIsNotNone(metrics.total_loss)
        self.assertGreaterEqual(metrics.total_loss, 0.0)

        # total_loss equals gross_loss (same definition).
        self.assertAlmostEqual(
            metrics.total_loss, metrics.gross_loss or 0.0, places=6
        )

        # total_loss_percentage is non-negative and consistent with
        # total_loss / initial_unallocated.
        if backtest_run.initial_unallocated:
            expected_pct = metrics.total_loss / backtest_run.initial_unallocated
            self.assertAlmostEqual(
                metrics.total_loss_percentage, expected_pct, places=6
            )
            self.assertGreaterEqual(metrics.total_loss_percentage, 0.0)
