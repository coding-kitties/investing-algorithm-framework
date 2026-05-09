"""
Python benchmark — runs a parameter sweep through the
investing-algorithm-framework's vectorized backtest engine
(`app.run_vector_backtests`).

This represents the *current* end-user code path: framework data
providers, the `TradingStrategy` lifecycle, signal generation in
pandas, vectorised execution, metric calculation and bundle write.
The wall-clock reported here is the baseline that future
Rust-accelerated kernels (epic #521 / iaf-core) need to beat.

Usage::

    python python_bench.py --combos 25 --workers 1 --years 10
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd

from investing_algorithm_framework import (
    BacktestDateRange,
    DataSource,
    DataType,
    PositionSize,
    TimeUnit,
    TradingCost,
    TradingStrategy,
    create_app,
)
from investing_algorithm_framework.infrastructure import (
    CSVOHLCVDataProvider,
)


REPO_DIR = Path(__file__).resolve().parent
DATA_DIR = REPO_DIR / "data"
RESULTS_DIR = REPO_DIR / "results"
BACKTEST_DIR = REPO_DIR / "backtest_results"

SYMBOLS = ["BTC-USD", "ETH-USD", "SOL-USD", "ADA-USD", "DOT-USD"]


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def _rsi(series: pd.Series, period: int) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1.0 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0.0, np.nan)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi.fillna(50.0)


class EmaRsiSweepStrategy(TradingStrategy):
    """Long-only EMA crossover with RSI oversold confirmation."""

    time_unit = TimeUnit.HOUR
    interval = 1

    def __init__(
        self,
        algorithm_id: str,
        symbols: list[str],
        trading_symbol: str,
        ema_short: int,
        ema_long: int,
        rsi_period: int,
        rsi_oversold: float,
        rsi_overbought: float,
        market: str = "BITVAVO",
        fee_pct: float = 0.1,
        slippage_pct: float = 0.05,
    ) -> None:
        warmup = max(ema_short, ema_long, rsi_period) + 10
        data_sources = [
            DataSource(
                identifier=f"ohlcv_{s}",
                data_type=DataType.OHLCV,
                time_frame="1h",
                market=market,
                symbol=f"{s}/USD",
                warmup_window=warmup,
                pandas=True,
            )
            for s in symbols
        ]
        position_sizes = [
            PositionSize(symbol=s, percentage_of_portfolio=1 / len(symbols))
            for s in symbols
        ]
        trading_costs = [
            TradingCost(
                symbol=s,
                fee_percentage=fee_pct,
                slippage_percentage=slippage_pct,
            )
            for s in symbols
        ]

        super().__init__(
            algorithm_id=algorithm_id,
            symbols=symbols,
            trading_symbol=trading_symbol,
            data_sources=data_sources,
            position_sizes=position_sizes,
            trading_costs=trading_costs,
            time_unit=self.time_unit,
            interval=self.interval,
        )
        self.ema_short = ema_short
        self.ema_long = ema_long
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.set_parameters(
            {
                "ema_short": ema_short,
                "ema_long": ema_long,
                "rsi_period": rsi_period,
                "rsi_oversold": rsi_oversold,
                "rsi_overbought": rsi_overbought,
            }
        )

    def generate_buy_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        signals: Dict[str, pd.Series] = {}
        for symbol in self.symbols:
            df = data[f"ohlcv_{symbol}"]
            close = df["Close"]
            ema_s = _ema(close, self.ema_short)
            ema_l = _ema(close, self.ema_long)
            rsi_v = _rsi(close, self.rsi_period)
            crossover = (ema_s > ema_l) & (ema_s.shift(1) <= ema_l.shift(1))
            sig = crossover & (rsi_v < self.rsi_oversold)
            signals[symbol] = sig.fillna(False).astype(bool)
        return signals

    def generate_sell_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        signals: Dict[str, pd.Series] = {}
        for symbol in self.symbols:
            df = data[f"ohlcv_{symbol}"]
            close = df["Close"]
            ema_s = _ema(close, self.ema_short)
            ema_l = _ema(close, self.ema_long)
            rsi_v = _rsi(close, self.rsi_period)
            crossunder = (ema_s < ema_l) & (ema_s.shift(1) >= ema_l.shift(1))
            sig = crossunder & (rsi_v > self.rsi_overbought)
            signals[symbol] = sig.fillna(False).astype(bool)
        return signals


def _build_param_grid(n_combos: int) -> list[dict]:
    rng = np.random.default_rng(0)
    short_choices = [10, 15, 20, 25, 30]
    long_choices = [50, 75, 100, 150, 200]
    rsi_periods = [7, 14, 21]
    rsi_oversold = [25, 30, 35]
    rsi_overbought = [65, 70, 75]
    grid = []
    seen = set()
    while len(grid) < n_combos:
        es = int(rng.choice(short_choices))
        el = int(rng.choice(long_choices))
        if el <= es:
            continue
        rp = int(rng.choice(rsi_periods))
        ro = int(rng.choice(rsi_oversold))
        rb = int(rng.choice(rsi_overbought))
        key = (es, el, rp, ro, rb)
        if key in seen:
            continue
        seen.add(key)
        grid.append(
            {
                "ema_short": es,
                "ema_long": el,
                "rsi_period": rp,
                "rsi_oversold": ro,
                "rsi_overbought": rb,
            }
        )
    return grid


def _data_date_bounds() -> tuple[datetime, datetime]:
    """Read the actual first/last datetime present in the generated CSVs."""
    df = pd.read_csv(DATA_DIR / f"{SYMBOLS[0]}.csv", usecols=["Datetime"])
    start = pd.to_datetime(df["Datetime"].iloc[0]).tz_localize("UTC")
    end = pd.to_datetime(df["Datetime"].iloc[-1]).tz_localize("UTC")
    return start.to_pydatetime(), end.to_pydatetime()


def _build_app(years: float) -> tuple:
    app = create_app()

    # Register one CSV provider per symbol so the framework treats
    # them as a normal market data source. Use a real market label
    # to avoid the framework trying to look "SYNTHETIC" up in CCXT.
    market = "BITVAVO"
    for symbol in SYMBOLS:
        app.add_data_provider(
            CSVOHLCVDataProvider(
                storage_path=str(DATA_DIR / f"{symbol}.csv"),
                symbol=f"{symbol}/USD",
                time_frame="1h",
                market=market,
            )
        )

    app.add_market(
        market=market,
        trading_symbol="USD",
        initial_balance=10_000,
    )

    data_start, data_end = _data_date_bounds()
    # Back end off so the framework can still request the next bar
    # for fills (it asks for `> end`).
    safe_end = data_end - pd.Timedelta(hours=24).to_pytimedelta()
    desired_start = safe_end - pd.Timedelta(
        days=int(years * 365.25)
    ).to_pytimedelta()
    # Clamp to actual data start with a warmup margin so that the
    # framework's per-strategy warmup_window (~210 hours for our
    # largest indicator) doesn't slide the first requested bar
    # outside the data range.
    safe_start = data_start + pd.Timedelta(days=20).to_pytimedelta()
    start = max(safe_start, desired_start)
    date_range = BacktestDateRange(
        start_date=start, end_date=safe_end, name=f"{int(years)}y"
    )
    return app, date_range, market


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--combos", type=int, default=25)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--years", type=float, default=10.0)
    parser.add_argument(
        "--results-file", type=Path,
        default=RESULTS_DIR / "python_bench.json"
    )
    args = parser.parse_args()

    if not (DATA_DIR / f"{SYMBOLS[0]}.csv").exists():
        raise SystemExit(
            "data/ is empty — run `python generate_data.py` first."
        )
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    app, date_range, market = _build_app(args.years)
    grid = _build_param_grid(args.combos)
    strategies = [
        EmaRsiSweepStrategy(
            algorithm_id=f"sweep_{i:03d}",
            symbols=SYMBOLS,
            trading_symbol="USD",
            market=market,
            **params,
        )
        for i, params in enumerate(grid)
    ]
    print(
        f"Python framework benchmark: {len(strategies)} strategies × "
        f"{len(SYMBOLS)} symbols, {args.years}y of hourly data, "
        f"workers={args.workers}"
    )

    if BACKTEST_DIR.exists():
        import shutil
        shutil.rmtree(BACKTEST_DIR)

    t0 = time.perf_counter()
    backtests = app.run_vector_backtests(
        strategies=strategies,
        backtest_date_ranges=[date_range],
        n_workers=args.workers,
        backtest_storage_directory=str(BACKTEST_DIR),
        show_progress=True,
    )
    elapsed = time.perf_counter() - t0

    n = len(backtests)
    summary = {
        "implementation": "python_framework",
        "n_strategies": len(strategies),
        "n_symbols": len(SYMBOLS),
        "n_backtests": n,
        "years": args.years,
        "workers": args.workers,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_backtests_per_second": round(n / elapsed, 3) if elapsed else 0.0,
        "wall_clock_per_backtest_ms": round(elapsed / n * 1000, 1) if n else 0.0,
    }
    args.results_file.parent.mkdir(parents=True, exist_ok=True)
    args.results_file.write_text(json.dumps(summary, indent=2))
    print()
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
