import unittest
from datetime import datetime, timezone

import pandas as pd

from investing_algorithm_framework.analysis.backtest_window_analysis import (
    analyze_backtest_windows,
    plot_backtest_windows,
    plot_window_correlation_matrix,
)
from investing_algorithm_framework.domain import BacktestDateRange, BacktestWindow


class TestPlotBacktestWindows(unittest.TestCase):

    def test_initial_zoom_is_forwarded_to_chart_spec(self):
        price_data = pd.DataFrame(
            {"Close": [100.0, 110.0]},
            index=pd.date_range("2024-01-01", periods=2, freq="h"),
        )

        spec = plot_backtest_windows(
            price_df=price_data,
            rolling_windows=[],
            initial_zoom=25,
        )

        self.assertEqual(
            spec.to_dict()["display"]["initialZoom"],
            25.0,
        )

    def test_side_by_side_creates_one_sliced_chart_per_window(self):
        price_data = pd.DataFrame(
            {"Close": [100.0, 101.0, 102.0, 103.0, 104.0]},
            index=pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC"),
        )
        windows = [
            BacktestWindow(
                train_range=BacktestDateRange(
                    datetime(2024, 1, 1, tzinfo=timezone.utc),
                    datetime(2024, 1, 2, tzinfo=timezone.utc),
                ),
                name="First",
            ),
            BacktestWindow(
                train_range=BacktestDateRange(
                    datetime(2024, 1, 3, tzinfo=timezone.utc),
                    datetime(2024, 1, 5, tzinfo=timezone.utc),
                ),
                name="Second",
            ),
        ]

        grid = plot_backtest_windows(
            price_df=price_data,
            rolling_windows=windows,
            variant="side-by-side",
        )

        self.assertEqual(len(grid.specs), 2)
        self.assertEqual(len(grid.specs[0].to_dict()["data"]["bars"]["time"]), 2)
        self.assertEqual(len(grid.specs[1].to_dict()["data"]["bars"]["time"]), 3)

    def test_unknown_variant_is_rejected(self):
        price_data = pd.DataFrame(
            {"Close": [100.0]},
            index=pd.date_range("2024-01-01", periods=1, freq="h"),
        )

        with self.assertRaisesRegex(ValueError, "variant must be"):
            plot_backtest_windows(
                price_df=price_data,
                rolling_windows=[],
                variant="unknown",
            )

    def test_correlation_matrix_returns_finterion_heatmap_spec(self):
        index = pd.date_range("2024-01-01", periods=4, freq="D")
        assets_data = {
            "BTC": pd.DataFrame({"Close": [100, 102, 101, 104]}, index=index),
            "ETH": pd.DataFrame({"Close": [50, 49, 51, 52]}, index=index),
        }

        spec = plot_window_correlation_matrix(assets_data)
        panel = spec.to_dict()["panels"][0]

        self.assertEqual(panel["kind"], "heatmap")
        self.assertEqual(panel["rows"], ["BTC", "ETH"])
        self.assertEqual(panel["cols"], ["BTC", "ETH"])
        self.assertEqual(panel["format"], "fixed2")
        self.assertEqual(panel["range"], 1.0)


if __name__ == "__main__":
    unittest.main()

class TestAnalyzeBacktestWindowsDownside(unittest.TestCase):
    """`analyze_backtest_windows` publishes downside_volatility and sortino_ratio."""

    def _window(self):
        import random

        random.seed(42)
        values = [1000.0]
        for _ in range(199):
            change = 0.002 if random.random() > 0.3 else -0.003
            values.append(values[-1] * (1 + change))
        index = pd.date_range("2024-01-01", periods=200, freq="D", tz="UTC")
        price_df = pd.DataFrame({"Close": values}, index=index)
        date_range = BacktestDateRange(
            datetime(2024, 1, 1, tzinfo=timezone.utc),
            datetime(2024, 7, 17, tzinfo=timezone.utc),
        )
        result = analyze_backtest_windows(
            {"window": (date_range, price_df)}, price_column="Close"
        )
        rows = result[1] if isinstance(result, tuple) else result
        return rows[0]

    def test_uniform_losses_do_not_collapse_downside_volatility(self):
        """Every losing day here is -0.3%, so their spread is ~0 but their risk is not.

        Measuring the dispersion among the losing periods instead of the
        shortfall over all of them drove downside_volatility to ~7e-14 and
        sortino_ratio past 1e14.
        """
        row = self._window()
        self.assertGreater(row["downside_volatility"], 0.01)
        self.assertLess(abs(row["sortino_ratio"]), 1000)

    def test_sharpe_is_unaffected_by_the_downside_definition(self):
        """Total volatility is a different quantity and must not move."""
        row = self._window()
        self.assertAlmostEqual(row["sharpe_ratio"], 1.8521697, places=5)
