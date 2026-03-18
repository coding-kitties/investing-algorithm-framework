from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock

from investing_algorithm_framework.domain import BacktestMetrics
from investing_algorithm_framework.app.reporting.tables.trade_metrics_table \
    import create_html_trade_metrics_table


class TestCreateHtmlTradeMetricsTable(TestCase):
    """
    Tests for create_html_trade_metrics_table.
    Regression tests for issue #352: KeyError on
    'trades_average_gain_percentage' / 'trades_average_loss_percentage'.
    """

    def _make_metrics(self, **overrides):
        """Create a BacktestMetrics with sensible defaults."""
        defaults = dict(
            backtest_start_date=datetime(
                2023, 1, 1, tzinfo=timezone.utc
            ),
            backtest_end_date=datetime(
                2023, 12, 31, tzinfo=timezone.utc
            ),
            trading_symbol="EUR",
            trades_per_year=12.0,
            trade_per_day=0.033,
            exposure_ratio=0.5,
            cumulative_exposure=180.0,
            average_trade_gain=50.0,
            average_trade_gain_percentage=5.0,
            average_trade_loss=-20.0,
            average_trade_loss_percentage=-2.0,
            average_trade_duration=48.0,
            number_of_trades=12,
            win_rate=60.0,
            win_loss_ratio=2.5,
            best_trade=None,
            worst_trade=None,
        )
        defaults.update(overrides)
        return BacktestMetrics(**defaults)

    def _make_report(self, trading_symbol="EUR"):
        """Create a mock report (BacktestRun) with trading_symbol."""
        report = MagicMock()
        report.trading_symbol = trading_symbol
        return report

    def test_no_keyerror_on_average_gain_loss_percentage(self):
        """
        Regression test for #352: create_html_trade_metrics_table
        must not raise KeyError for 'trades_average_gain_percentage'
        or 'trades_average_loss_percentage'.
        """
        metrics = self._make_metrics()
        report = self._make_report()
        # This would raise KeyError before the fix
        html = create_html_trade_metrics_table(metrics, report)
        self.assertIsInstance(html, str)
        self.assertIn("5.00%", html)   # average_trade_gain_percentage
        self.assertIn("-2.00%", html)   # average_trade_loss_percentage

    def test_output_contains_all_metrics(self):
        """Verify all expected metric labels appear in the HTML output."""
        metrics = self._make_metrics()
        report = self._make_report()
        html = create_html_trade_metrics_table(metrics, report)
        expected_labels = [
            "Trades per Year",
            "Trade per Day",
            "Exposure Ratio",
            "Cumulative Exposure",
            "Trades Average Gain",
            "Trades Average Loss",
            "Best Trade",
            "Worst Trade",
            "Average Trade Duration",
            "Number of Trades",
            "Win Rate",
            "Win/Loss Ratio",
        ]
        for label in expected_labels:
            self.assertIn(label, html, f"Missing metric: {label}")

    def test_with_best_and_worst_trade(self):
        """Verify best/worst trade dicts are handled correctly."""
        metrics = self._make_metrics(
            best_trade=MagicMock(**{
                "to_dict.return_value": {
                    "net_gain": 120.50,
                    "opened_at": datetime(
                        2023, 6, 15, tzinfo=timezone.utc
                    ),
                }
            }),
            worst_trade=MagicMock(**{
                "to_dict.return_value": {
                    "net_gain": -45.30,
                    "opened_at": datetime(
                        2023, 9, 3, tzinfo=timezone.utc
                    ),
                }
            }),
        )
        report = self._make_report()
        html = create_html_trade_metrics_table(metrics, report)
        self.assertIn("120.50", html)
        self.assertIn("-45.30", html)

    def test_with_none_best_worst_trade(self):
        """Verify N/A is shown when best/worst trades are None."""
        metrics = self._make_metrics(
            best_trade=None,
            worst_trade=None
        )
        report = self._make_report()
        html = create_html_trade_metrics_table(metrics, report)
        self.assertIn("N/A", html)
