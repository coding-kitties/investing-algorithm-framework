import unittest
from datetime import datetime, timezone

import pandas as pd

from investing_algorithm_framework.analysis.backtest_window_analysis import (
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