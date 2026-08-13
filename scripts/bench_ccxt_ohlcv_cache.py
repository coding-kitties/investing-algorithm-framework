"""Benchmark: canonical merge-and-slice OHLCV cache vs. no cross-window reuse.

`CCXTOHLCVDataProvider` used to save every downloaded window under a
date-range-suffixed file name (`OHLCV_<SYMBOL>_<MARKET>_<TF>_<START>_<END>.csv`).
Any request whose date range wasn't *fully contained* in an existing file
(the common case for overlapping/walk-forward backtest windows) triggered a
full re-download of the entire requested range.

The canonical cache keeps a single, date-range-free file per
(symbol, market, time_frame) and only downloads the sub-range(s) not yet
covered, merging them into that file. This script simulates a walk-forward
sweep of overlapping windows, across several different symbols, time
frames, and date ranges, and compares:

* "No cross-window reuse": each window re-downloads its full range from
  scratch (the old behavior for any window that isn't an exact re-run).
* "Canonical merge-and-slice cache": each window only downloads its new
  incremental delta.

Network access is mocked out with a synthetic OHLCV generator; the simulated
per-request latency is proportional to the number of candles requested, which
models CCXT's rate-limited pagination (`sleep(exchange.rateLimit / 1000)` per
page fetched in `CCXTOHLCVDataProvider.get_ohlcv`).

Run with::

    python scripts/bench_ccxt_ohlcv_cache.py
"""
from __future__ import annotations

import shutil
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Tuple
from unittest.mock import patch

import polars as pl

from investing_algorithm_framework.domain import TimeFrame
from investing_algorithm_framework.infrastructure.data_providers.ccxt import (
    CCXTOHLCVDataProvider,
)

# Simulated per-candle exchange latency (models rate-limited pagination).
LATENCY_PER_CANDLE_SECONDS = 0.0005


@dataclass(frozen=True)
class Scenario:
    """A walk-forward sweep of overlapping windows for one
    symbol/market/time_frame combination, e.g. what a rolling backtest
    study or a parameter sweep repeatedly re-runs."""
    label: str
    symbol: str
    market: str
    time_frame: str
    base_start: datetime
    n_windows: int
    window_days: int
    step_days: int


SCENARIOS = [
    Scenario(
        label="BTC/EUR 2h, 30d window / 5d step",
        symbol="BTC/EUR",
        market="BITVAVO",
        time_frame="2h",
        base_start=datetime(2023, 1, 1, tzinfo=timezone.utc),
        n_windows=20,
        window_days=30,
        step_days=5,
    ),
    Scenario(
        label="ETH/EUR 1h, 14d window / 3d step",
        symbol="ETH/EUR",
        market="BITVAVO",
        time_frame="1h",
        base_start=datetime(2023, 6, 1, tzinfo=timezone.utc),
        n_windows=15,
        window_days=14,
        step_days=3,
    ),
    Scenario(
        label="SOL/EUR 1d, 90d window / 10d step",
        symbol="SOL/EUR",
        market="BINANCE",
        time_frame="1d",
        base_start=datetime(2022, 1, 1, tzinfo=timezone.utc),
        n_windows=10,
        window_days=90,
        step_days=10,
    ),
    Scenario(
        label="BTC/USDT 15m, 7d window / 1d step",
        symbol="BTC/USDT",
        market="BINANCE",
        time_frame="15m",
        base_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        n_windows=25,
        window_days=7,
        step_days=1,
    ),
]


def _make_ohlcv(start: datetime, end: datetime, minutes: int) -> pl.DataFrame:
    """Deterministic, synthetic OHLCV candles at a fixed interval."""
    n = int((end - start).total_seconds() // (minutes * 60)) + 1
    dates = [start + timedelta(minutes=minutes * i) for i in range(n)]
    prices = [100.0 + i * 0.01 for i in range(n)]
    return pl.DataFrame(
        {
            "Datetime": dates,
            "Open": prices,
            "High": prices,
            "Low": prices,
            "Close": prices,
            "Volume": [1.0] * n,
        }
    )


def _fake_get_ohlcv(
    self, symbol, time_frame, from_timestamp, market, to_timestamp=None
):
    tf = time_frame.value if hasattr(time_frame, "value") else time_frame
    minutes = TimeFrame.from_value(tf).amount_of_minutes
    data = _make_ohlcv(from_timestamp, to_timestamp, minutes)
    time.sleep(LATENCY_PER_CANDLE_SECONDS * len(data))
    return data


def _instrumented(base_fn):
    """Wraps `base_fn` to record call/candle counts without changing
    behavior."""
    stats = {"calls": 0, "candles": 0}

    def wrapper(self, *args, **kwargs):
        data = base_fn(self, *args, **kwargs)
        stats["calls"] += 1
        stats["candles"] += len(data)
        return data

    return wrapper, stats


def _make_windows(scenario: Scenario) -> List[Tuple[datetime, datetime]]:
    windows = []
    for i in range(scenario.n_windows):
        start = scenario.base_start + timedelta(days=i * scenario.step_days)
        end = start + timedelta(days=scenario.window_days)
        windows.append((start, end))
    return windows


def run_without_reuse(
    scenario: Scenario, storage_dir: str, windows
) -> Tuple[float, int, int]:
    """Old behavior: every window is a guaranteed cache miss that
    re-downloads its full range."""
    wrapper, stats = _instrumented(_fake_get_ohlcv)
    t0 = time.perf_counter()

    with patch.object(CCXTOHLCVDataProvider, "get_ohlcv", wrapper):
        for start, end in windows:
            provider = CCXTOHLCVDataProvider(
                symbol=scenario.symbol,
                market=scenario.market,
                time_frame=scenario.time_frame,
                storage_directory=storage_dir,
            )
            data = provider.get_ohlcv(
                symbol=scenario.symbol,
                time_frame=TimeFrame.from_value(scenario.time_frame),
                from_timestamp=start,
                market=scenario.market,
                to_timestamp=end,
            )
            assert len(data) > 0

    return time.perf_counter() - t0, stats["calls"], stats["candles"]


def run_with_canonical_cache(
    scenario: Scenario, storage_dir: str, windows
) -> Tuple[float, int, int]:
    """New behavior: only the missing delta is downloaded and merged
    into the canonical cache file."""
    wrapper, stats = _instrumented(_fake_get_ohlcv)
    t0 = time.perf_counter()

    with patch.object(CCXTOHLCVDataProvider, "get_ohlcv", wrapper):
        for start, end in windows:
            provider = CCXTOHLCVDataProvider(
                symbol=scenario.symbol,
                market=scenario.market,
                time_frame=scenario.time_frame,
                storage_directory=storage_dir,
            )
            data = provider.get_data(start_date=start, end_date=end, save=True)
            assert len(data) > 0

    return time.perf_counter() - t0, stats["calls"], stats["candles"]


def run_scenario(scenario: Scenario) -> dict:
    windows = _make_windows(scenario)

    no_reuse_dir = tempfile.mkdtemp(prefix="bench-no-reuse-")
    try:
        no_reuse_time, no_reuse_calls, no_reuse_candles = run_without_reuse(
            scenario, no_reuse_dir, windows
        )
    finally:
        shutil.rmtree(no_reuse_dir, ignore_errors=True)

    cache_dir = tempfile.mkdtemp(prefix="bench-cache-")
    try:
        cache_time, cache_calls, cache_candles = run_with_canonical_cache(
            scenario, cache_dir, windows
        )
    finally:
        shutil.rmtree(cache_dir, ignore_errors=True)

    return {
        "scenario": scenario,
        "no_reuse_time": no_reuse_time,
        "no_reuse_calls": no_reuse_calls,
        "no_reuse_candles": no_reuse_candles,
        "cache_time": cache_time,
        "cache_calls": cache_calls,
        "cache_candles": cache_candles,
    }


def _print_result(result: dict) -> None:
    scenario = result["scenario"]
    print(
        f"{scenario.label}\n"
        f"  {scenario.n_windows} windows, {scenario.window_days}d window / "
        f"{scenario.step_days}d step, {scenario.symbol} {scenario.time_frame} "
        f"{scenario.market}"
    )
    header = f"  {'Approach':<30}{'Calls':<8}{'Candles':<12}{'Wall time (s)':<15}"
    print(header)
    print("  " + "-" * (len(header) - 2))
    print(
        f"  {'No cross-window reuse':<30}{result['no_reuse_calls']:<8}"
        f"{result['no_reuse_candles']:<12}{result['no_reuse_time']:<15.2f}"
    )
    print(
        f"  {'Canonical merge-and-slice':<30}{result['cache_calls']:<8}"
        f"{result['cache_candles']:<12}{result['cache_time']:<15.2f}"
    )
    print(
        f"  Speedup: {result['no_reuse_time'] / result['cache_time']:.1f}x "
        f"wall time, "
        f"{result['no_reuse_candles'] / result['cache_candles']:.1f}x "
        f"fewer candles downloaded\n"
    )


def main() -> None:
    print(
        f"Simulated exchange latency: "
        f"{LATENCY_PER_CANDLE_SECONDS * 1000:.2f}ms/candle "
        f"(models rate-limited pagination)\n"
    )

    results = [run_scenario(scenario) for scenario in SCENARIOS]

    for result in results:
        _print_result(result)

    total_no_reuse_time = sum(r["no_reuse_time"] for r in results)
    total_cache_time = sum(r["cache_time"] for r in results)
    total_no_reuse_candles = sum(r["no_reuse_candles"] for r in results)
    total_cache_candles = sum(r["cache_candles"] for r in results)

    print(
        f"Overall across {len(results)} scenarios: "
        f"{total_no_reuse_time / total_cache_time:.1f}x wall time, "
        f"{total_no_reuse_candles / total_cache_candles:.1f}x fewer "
        f"candles downloaded"
    )


if __name__ == "__main__":
    main()
