"""Unit tests for built-in Pipeline factors and rank/top/bottom ops."""
from __future__ import annotations

import math
from datetime import datetime, timedelta

import polars as pl
import pytest

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


def test_returns_simple_percent_return():
    panel = _panel({"X": [_bar(i, c) for i, c in enumerate([10, 11, 12, 13])]})
    series = Returns(window=2).compute_panel(panel).to_list()
    # Bar 0,1 → null; bar 2 → 12/10 - 1; bar 3 → 13/11 - 1
    assert series[0] is None and series[1] is None
    assert series[2] == pytest.approx(0.2)
    assert series[3] == pytest.approx(13.0 / 11.0 - 1.0)


def test_average_dollar_volume_rolling_mean():
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
    assert series[0] is None
    assert series[1] == pytest.approx(25.0)
    assert series[2] == pytest.approx(65.0)
    assert series[3] == pytest.approx(125.0)


def test_sma_rolling_mean():
    panel = _panel({"X": [_bar(i, c) for i, c in enumerate([1, 2, 3, 4, 5])]})
    series = SMA(window=3).compute_panel(panel).to_list()
    assert series[0] is None and series[1] is None
    assert series[2] == pytest.approx(2.0)
    assert series[3] == pytest.approx(3.0)
    assert series[4] == pytest.approx(4.0)


def test_volatility_log_return_stdev_scaled():
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
    log_rets = [math.log(closes[i] / closes[i - 1]) for i in range(1, len(closes))]
    last_window = log_rets[-window:]
    mean = sum(last_window) / window
    var = sum((x - mean) ** 2 for x in last_window) / (window - 1)
    expected = math.sqrt(var) * math.sqrt(pp_year)
    assert series[-1] == pytest.approx(expected)


def test_rsi_all_gains_returns_100():
    panel = _panel({"X": [_bar(i, c) for i, c in enumerate(range(1, 20))]})
    series = RSI(window=4).compute_panel(panel).to_list()
    # All gains, no losses → avg_loss == 0 → RSI clamped to 100
    assert series[-1] == pytest.approx(100.0)


def test_rsi_with_losses_strictly_between_0_and_100():
    closes = [100, 102, 101, 103, 99, 104, 100, 106, 101]
    panel = _panel({"X": [_bar(i, c) for i, c in enumerate(closes)]})
    series = RSI(window=4).compute_panel(panel).to_list()
    last = series[-1]
    assert last is not None
    assert 0.0 < last < 100.0


def test_factor_rank_orders_within_each_bar():
    # 3 symbols, 1 bar of meaningful data — but rank needs Returns(window=1).
    panel = _panel(
        {
            "AAA": [_bar(0, 100), _bar(1, 110)],  # +10%
            "BBB": [_bar(0, 100), _bar(1, 105)],  # +5%
            "CCC": [_bar(0, 100), _bar(1, 120)],  # +20%
        }
    )
    ranked = Returns(window=1).rank().compute_panel(panel)
    df = panel.select(["datetime", "symbol"]).with_columns(
        ranked.alias("rk")
    ).filter(pl.col("datetime") == datetime(2024, 1, 2))
    out = {row["symbol"]: row["rk"] for row in df.to_dicts()}
    # Ascending ordinal ranks: BBB=1, AAA=2, CCC=3
    assert out["BBB"] == 1.0
    assert out["AAA"] == 2.0
    assert out["CCC"] == 3.0


def test_factor_top_filter_keeps_highest():
    panel = _panel(
        {
            "AAA": [_bar(0, 100), _bar(1, 110)],
            "BBB": [_bar(0, 100), _bar(1, 105)],
            "CCC": [_bar(0, 100), _bar(1, 120)],
        }
    )
    mask = Returns(window=1).top(2).compute_panel(panel)
    df = panel.select(["datetime", "symbol"]).with_columns(
        mask.alias("m")
    ).filter(pl.col("datetime") == datetime(2024, 1, 2))
    out = {row["symbol"]: row["m"] for row in df.to_dicts()}
    # Top 2 by descending returns: CCC (20%) and AAA (10%)
    assert out["AAA"] is True
    assert out["CCC"] is True
    assert out["BBB"] is False


def test_factor_bottom_filter_keeps_lowest():
    panel = _panel(
        {
            "AAA": [_bar(0, 100), _bar(1, 110)],
            "BBB": [_bar(0, 100), _bar(1, 105)],
            "CCC": [_bar(0, 100), _bar(1, 120)],
        }
    )
    mask = Returns(window=1).bottom(1).compute_panel(panel)
    df = panel.select(["datetime", "symbol"]).with_columns(
        mask.alias("m")
    ).filter(pl.col("datetime") == datetime(2024, 1, 2))
    out = {row["symbol"]: row["m"] for row in df.to_dicts()}
    assert out["BBB"] is True
    assert out["AAA"] is False
    assert out["CCC"] is False


def test_factor_invalid_window_raises():
    with pytest.raises(ValueError):
        Returns(window=0)


def test_volatility_invalid_periods_raises():
    with pytest.raises(ValueError):
        Volatility(window=10, periods_per_year=0)
