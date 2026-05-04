"""Unit tests for built-in Pipeline factors and rank/top/bottom ops."""
from __future__ import annotations

import math
import unittest
from datetime import datetime, timedelta

import polars as pl

from investing_algorithm_framework import (
    AverageDollarVolume,
    RSI,
    Returns,
    SMA,
    Volatility,
)


def _panel(data):
    """Build a long-form panel from ``{symbol: [(dt, o, h, l, c, v), ...]}``.

    The engine expects columns sorted by ``(symbol, datetime)``.
    """
    rows = []
    for symbol, bars in data.items():
        for dt, o, h, l, c, v in bars:
            rows.append(
                {
                    "datetime": dt,
                    "symbol": symbol,
                    "open": float(o),
                    "high": float(h),
                    "low": float(l),
                    "close": float(c),
                    "volume": float(v),
                }
            )
    return pl.DataFrame(rows).sort(["symbol", "datetime"])


def _bar(dt_idx, close, volume=1.0):
    dt = datetime(2024, 1, 1) + timedelta(days=dt_idx)
    return (dt, close, close, close, close, volume)


class TestPipelineFactors(unittest.TestCase):

    def test_returns_simple_percent_return(self):
        panel = _panel(
            {"X": [_bar(i, c) for i, c in enumerate([10, 11, 12, 13])]}
        )
        series = Returns(window=2).compute_panel(panel).to_list()
        # Bar 0,1 → null; bar 2 → 12/10 - 1; bar 3 → 13/11 - 1
        self.assertIsNone(series[0])
        self.assertIsNone(series[1])
        self.assertAlmostEqual(series[2], 0.2)
        self.assertAlmostEqual(series[3], 13.0 / 11.0 - 1.0)

    def test_average_dollar_volume_rolling_mean(self):
        panel = _panel(
            {
                "X": [
                    (datetime(2024, 1, 1) + timedelta(days=i), c, c, c, c, vol)
                    for i, (c, vol) in enumerate(
                        [(10, 1), (20, 2), (30, 3), (40, 4)]
                    )
                ]
            }
        )
        series = AverageDollarVolume(window=2).compute_panel(panel).to_list()
        # close*volume = [10, 40, 90, 160]; rolling mean window=2
        self.assertIsNone(series[0])
        self.assertAlmostEqual(series[1], 25.0)
        self.assertAlmostEqual(series[2], 65.0)
        self.assertAlmostEqual(series[3], 125.0)

    def test_sma_rolling_mean(self):
        panel = _panel(
            {"X": [_bar(i, c) for i, c in enumerate([1, 2, 3, 4, 5])]}
        )
        series = SMA(window=3).compute_panel(panel).to_list()
        self.assertIsNone(series[0])
        self.assertIsNone(series[1])
        self.assertAlmostEqual(series[2], 2.0)
        self.assertAlmostEqual(series[3], 3.0)
        self.assertAlmostEqual(series[4], 4.0)

    def test_volatility_log_return_stdev_scaled(self):
        closes = [100.0, 101.0, 99.0, 102.0, 100.0, 103.0]
        panel = _panel({"X": [_bar(i, c) for i, c in enumerate(closes)]})
        window = 4
        pp_year = 252
        series = (
            Volatility(window=window, periods_per_year=pp_year)
            .compute_panel(panel)
            .to_list()
        )
        # Manually compute the last value
        log_rets = [
            math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))
        ]
        last_window = log_rets[-window:]
        mean = sum(last_window) / window
        var = sum((x - mean) ** 2 for x in last_window) / (window - 1)
        expected = math.sqrt(var) * math.sqrt(pp_year)
        self.assertAlmostEqual(series[-1], expected)

    def test_rsi_all_gains_returns_100(self):
        panel = _panel(
            {"X": [_bar(i, c) for i, c in enumerate(range(1, 20))]}
        )
        series = RSI(window=4).compute_panel(panel).to_list()
        # All gains, no losses → avg_loss == 0 → RSI clamped to 100
        self.assertAlmostEqual(series[-1], 100.0)

    def test_rsi_with_losses_strictly_between_0_and_100(self):
        closes = [100, 102, 101, 103, 99, 104, 100, 106, 101]
        panel = _panel({"X": [_bar(i, c) for i, c in enumerate(closes)]})
        series = RSI(window=4).compute_panel(panel).to_list()
        last = series[-1]
        self.assertIsNotNone(last)
        self.assertGreater(last, 0.0)
        self.assertLess(last, 100.0)

    def test_factor_rank_orders_within_each_bar(self):
        # 3 symbols, 1 bar of meaningful data — rank needs Returns(window=1).
        panel = _panel(
            {
                "AAA": [_bar(0, 100), _bar(1, 110)],  # +10%
                "BBB": [_bar(0, 100), _bar(1, 105)],  # +5%
                "CCC": [_bar(0, 100), _bar(1, 120)],  # +20%
            }
        )
        ranked = Returns(window=1).rank().compute_panel(panel)
        df = (
            panel.select(["datetime", "symbol"])
            .with_columns(ranked.alias("rk"))
            .filter(pl.col("datetime") == datetime(2024, 1, 2))
        )
        out = {row["symbol"]: row["rk"] for row in df.to_dicts()}
        # Ascending ordinal ranks: BBB=1, AAA=2, CCC=3
        self.assertEqual(out["BBB"], 1.0)
        self.assertEqual(out["AAA"], 2.0)
        self.assertEqual(out["CCC"], 3.0)

    def test_factor_top_filter_keeps_highest(self):
        panel = _panel(
            {
                "AAA": [_bar(0, 100), _bar(1, 110)],
                "BBB": [_bar(0, 100), _bar(1, 105)],
                "CCC": [_bar(0, 100), _bar(1, 120)],
            }
        )
        mask = Returns(window=1).top(2).compute_panel(panel)
        df = (
            panel.select(["datetime", "symbol"])
            .with_columns(mask.alias("m"))
            .filter(pl.col("datetime") == datetime(2024, 1, 2))
        )
        out = {row["symbol"]: row["m"] for row in df.to_dicts()}
        # Top 2 by descending returns: CCC (20%) and AAA (10%)
        self.assertTrue(out["AAA"])
        self.assertTrue(out["CCC"])
        self.assertFalse(out["BBB"])

    def test_factor_bottom_filter_keeps_lowest(self):
        panel = _panel(
            {
                "AAA": [_bar(0, 100), _bar(1, 110)],
                "BBB": [_bar(0, 100), _bar(1, 105)],
                "CCC": [_bar(0, 100), _bar(1, 120)],
            }
        )
        mask = Returns(window=1).bottom(1).compute_panel(panel)
        df = (
            panel.select(["datetime", "symbol"])
            .with_columns(mask.alias("m"))
            .filter(pl.col("datetime") == datetime(2024, 1, 2))
        )
        out = {row["symbol"]: row["m"] for row in df.to_dicts()}
        self.assertTrue(out["BBB"])
        self.assertFalse(out["AAA"])
        self.assertFalse(out["CCC"])

    def test_factor_invalid_window_raises(self):
        with self.assertRaises(ValueError):
            Returns(window=0)

    def test_volatility_invalid_periods_raises(self):
        with self.assertRaises(ValueError):
            Volatility(window=10, periods_per_year=0)


if __name__ == "__main__":
    unittest.main()
