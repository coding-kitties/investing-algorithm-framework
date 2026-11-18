"""Trade-average summaries use the producer's winning and losing counts."""
import unittest
from types import SimpleNamespace

from investing_algorithm_framework.domain import (
    BacktestDateRange, BacktestMetrics, BacktestWindow, TradeStatus,
)
from investing_algorithm_framework.domain.backtesting.combine_backtests \
    import generate_backtest_summary_metrics
from investing_algorithm_framework.services.metrics.trades import (
    get_negative_trades, get_positive_trades,
)
from investing_algorithm_framework.services.metrics import win_rate


def window_metrics(wins, losses, breakevens, gain, loss):
    trades = [
        SimpleNamespace(status=TradeStatus.CLOSED, net_gain=value,
                        net_gain_absolute=value)
        for value in ([gain] * wins + [loss] * losses + [0] * breakevens)
    ]
    return BacktestMetrics(
        backtest_window=BacktestWindow(BacktestDateRange(
            "2024-01-01", "2024-02-01")),
        initial_unallocated=1000,
        number_of_trades=len(trades),
        number_of_trades_closed=len(trades),
        number_of_positive_trades=get_positive_trades(trades)[0],
        number_of_negative_trades=get_negative_trades(trades)[0],
        win_rate=win_rate.get_win_rate(trades),
        average_trade_gain=gain if wins else 0,
        average_trade_gain_percentage=gain / 100 if wins else 0,
        average_trade_loss=loss if losses else 0,
        average_trade_loss_percentage=loss / 100 if losses else 0,
    )


class TestTradeAveragePopulations(unittest.TestCase):
    def test_fractional_win_rates(self):
        metrics = [window_metrics(90, 10, 0, 20, -10),
                   window_metrics(10, 90, 0, 200, -100)]
        summary = generate_backtest_summary_metrics(metrics)
        self.assertAlmostEqual(summary.average_trade_loss, -91)
        self.assertAlmostEqual(summary.average_trade_loss_percentage, -0.91)
        self.assertAlmostEqual(summary.average_trade_gain, 38)
        self.assertAlmostEqual(summary.average_trade_gain_percentage, 0.38)
        self.assertAlmostEqual(summary.win_rate, 0.5)

    def test_breakevens_are_not_losses(self):
        metrics = [window_metrics(2, 1, 7, 10, -10),
                   window_metrics(3, 9, 8, 20, -100)]
        summary = generate_backtest_summary_metrics(metrics)
        self.assertAlmostEqual(summary.average_trade_loss, -91)
        self.assertAlmostEqual(summary.average_trade_loss_percentage, -0.91)
        self.assertAlmostEqual(summary.average_trade_gain, 16)
        self.assertAlmostEqual(summary.average_trade_gain_percentage, 0.16)
        self.assertAlmostEqual(summary.win_rate, 5 / 30)

    def test_empty_populations_do_not_contribute(self):
        for wins, losses in [(0, 0), (3, 0), (0, 4)]:
            with self.subTest(wins=wins, losses=losses):
                summary = generate_backtest_summary_metrics([
                    window_metrics(wins, losses, 2, 10, -20),
                    window_metrics(0, 0, 0, 10, -20),
                ])
                self.assertEqual(summary.average_trade_gain,
                                 10 if wins else None)
                self.assertEqual(summary.average_trade_loss,
                                 -20 if losses else None)

    def test_saved_metrics_recompute_with_same_populations(self):
        metrics = [window_metrics(2, 1, 7, 10, -10),
                   window_metrics(3, 9, 8, 20, -100)]
        restored = [BacktestMetrics.from_dict(m.to_dict()) for m in metrics]
        summary = generate_backtest_summary_metrics(restored)
        self.assertAlmostEqual(summary.average_trade_loss, -91)
        self.assertAlmostEqual(summary.average_trade_gain, 16)
        self.assertAlmostEqual(summary.win_rate, 5 / 30)

    def test_legacy_saved_count_pairs(self):
        metrics = [window_metrics(2, 1, 7, 10, -10),
                   window_metrics(3, 9, 8, 20, -100)]
        restored = []
        for m in metrics:
            saved = m.to_dict()
            saved["number_of_positive_trades"] = [
                m.number_of_positive_trades, m.win_rate * 100,
            ]
            saved["number_of_negative_trades"] = [
                m.number_of_negative_trades,
                m.number_of_negative_trades / m.number_of_trades_closed * 100,
            ]
            restored.append(BacktestMetrics.from_dict(saved))
        summary = generate_backtest_summary_metrics(restored)
        self.assertAlmostEqual(summary.average_trade_loss, -91)
        self.assertAlmostEqual(summary.average_trade_gain, 16)

    def test_unavailable_counts_do_not_invent_a_population(self):
        metrics = window_metrics(2, 1, 7, 10, -10)
        metrics.number_of_positive_trades = None
        metrics.number_of_negative_trades = None
        summary = generate_backtest_summary_metrics([metrics])
        self.assertIsNone(summary.average_trade_gain)
        self.assertIsNone(summary.average_trade_loss)
