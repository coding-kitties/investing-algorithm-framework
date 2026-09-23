"""Offline A/B benchmark for vector lifecycle lookup or trading-loop inputs.

Run with Poetry from the repository root using python -m scripts.<module>.
This measures one vector engine process, not streaming or a 50-worker sweep.
"""
import argparse
import gc
import hashlib
import json
import math
import platform
from statistics import median
from time import perf_counter
import tracemalloc
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from investing_algorithm_framework import (
    BacktestDateRange, DataSource, PortfolioConfiguration, PositionSize,
    Schedule, SignalSeries, SignalSide, TimeUnit, TradingStrategy,
)
from investing_algorithm_framework.infrastructure.services.backtesting \
    import vector_backtest_service as vector_module


class LegacyScan:
    """Return every trade, recreating the old inner loop exactly."""

    def __init__(self, trades):
        self.trades = trades

    def get(self, timestamp, default=()):
        return self.trades


def lookup_benchmark(bars, repeats):
    timestamps = list(pd.date_range(
        "2025-01-01", periods=bars, freq="h", tz="UTC"
    ).to_pydatetime())
    trades = [SimpleNamespace(opened_at=timestamps[index],
                              closed_at=timestamps[index + 2])
              for index in range(0, bars - 2, 4)]
    timings = {"legacy": [], "indexed": []}
    for repeat in range(repeats):
        names = ("legacy", "indexed") if repeat % 2 == 0 else (
            "indexed", "legacy"
        )
        for name in names:
            start = perf_counter()
            events = (LegacyScan(trades) if name == "legacy" else
                      vector_module._index_snapshot_trade_events(trades))
            count = 0
            for timestamp in timestamps:
                for trade in events.get(timestamp, ()):
                    count += trade.opened_at == timestamp
                    count += trade.closed_at == timestamp
            timings[name].append(perf_counter() - start)
            if count != 2 * len(trades):
                raise AssertionError("Lifecycle event count differs")
    tracemalloc.start()
    events = vector_module._index_snapshot_trade_events(trades)
    _, peak_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "bars": bars, "trades": len(trades),
        "lookup_seconds": {name: median(values)
                           for name, values in timings.items()},
        "index_peak_python_bytes": peak_bytes,
        "indexed_trade_references": sum(map(len, events.values())),
    }


class CyclingStrategy(TradingStrategy):
    def __init__(self, symbols):
        super().__init__(
            algorithm_id="snapshot-benchmark",
            data_sources=[DataSource(
                symbol=f"{symbol}/EUR", market="BITVAVO",
                data_type="ohlcv", time_frame="1h", pandas=True,
                identifier=f"{symbol}/EUR",
            ) for symbol in symbols],
            symbols=symbols, schedule=Schedule.every(1, TimeUnit.HOUR),
            position_sizes=[PositionSize(
                symbol=symbol, percentage_of_portfolio=40 / len(symbols)
            ) for symbol in symbols],
        )

    def generate_signal_series(self, data):
        for symbol in self.symbols:
            index = data[f"{symbol}/EUR"].index
            for side, offset in (
                (SignalSide.OPEN_LONG, 0), (SignalSide.CLOSE_LONG, 2),
                (SignalSide.OPEN_SHORT, 4), (SignalSide.CLOSE_SHORT, 6),
            ):
                yield SignalSeries(
                    symbol=symbol, side=side,
                    series=pd.Series(
                        [row % 8 == offset for row in range(len(index))],
                        index=index,
                    ),
                )


def workload(bars, symbol_count):
    index = pd.date_range("2025-01-01", periods=bars, freq="h", tz="UTC")
    symbols = [f"ASSET{number}" for number in range(symbol_count)]
    frames = {}
    for number, symbol in enumerate(symbols):
        prices = [100 + number + math.sin(row / 5)
                  for row in range(bars)]
        frames[f"{symbol}/EUR"] = pd.DataFrame({
            "Open": prices, "High": prices, "Low": prices,
            "Close": prices, "Volume": 1000.0,
        }, index=index)
    provider = SimpleNamespace(
        get_vectorized_backtest_data=lambda **kwargs: frames,
        get_ohlcv_data=lambda symbol, **kwargs: frames[symbol],
    )
    return vector_module.VectorBacktestService(provider), {
        "strategy": CyclingStrategy(symbols),
        "backtest_date_range": BacktestDateRange(
            start_date=index[0].to_pydatetime(),
            end_date=index[-1].to_pydatetime(),
        ),
        "portfolio_configuration": PortfolioConfiguration(
            market="BITVAVO", trading_symbol="EUR", initial_balance=10000,
        ),
    }


def result_payload(result):
    def without_generated_ids(value):
        if isinstance(value, dict):
            return {key: without_generated_ids(item)
                    for key, item in value.items()
                    if key not in ("id", "portfolio_id")}
        if isinstance(value, (list, tuple)):
            return [without_generated_ids(item) for item in value]
        return value

    payload = {
        "snapshots": [item.to_dict() for item in result.portfolio_snapshots],
        "trades": [item.to_dict() for item in result.trades],
        "orders": [item.to_dict() for item in result.orders],
        "positions": [item.to_dict() for item in result.positions],
        "metrics": result.backtest_metrics.to_dict(),
        "signals": result.signal_events,
    }
    return json.loads(json.dumps(
        without_generated_ids(payload), sort_keys=True, default=str
    ))


def result_digest(result):
    return hashlib.sha256(json.dumps(
        result_payload(result), sort_keys=True
    ).encode()).hexdigest()


def engine_benchmark(bars, symbols, repeats, loop_inputs=False,
                     native_loop=False):
    if native_loop:
        factories = {
            "python": vector_module._loop_values,
            "rust": vector_module._loop_values,
        }
        target = "_loop_values"
    elif loop_inputs:
        factories = {
            "pandas": lambda series: series.iloc,
            "arrays": vector_module._loop_values,
        }
        target = "_loop_values"
    else:
        factories = {
            "legacy": LegacyScan,
            "indexed": vector_module._index_snapshot_trade_events,
        }
        target = "_index_snapshot_trade_events"
    timings = {name: [] for name in factories}
    expected_digest = None
    counts = None
    for repeat in range(repeats + 1):
        names = list(factories)
        if repeat % 2:
            names.reverse()
        for name in names:
            service, arguments = workload(bars, symbols)
            if native_loop:
                arguments['execution_backend'] = name
            gc.collect()
            with patch.object(vector_module, target,
                              wraps=factories[name]) as lookup:
                start = perf_counter()
                result = service.run(**arguments)
                elapsed = perf_counter() - start
                if loop_inputs or native_loop:
                    if lookup.call_count != symbols * 7:
                        raise AssertionError("Unexpected input preparation")
                else:
                    lookup.assert_called_once()
            digest = result_digest(result)
            if expected_digest is None:
                expected_digest = digest
            elif digest != expected_digest:
                raise AssertionError("Snapshots/trades/metrics differ")
            counts = {"trades": len(result.trades),
                      "snapshots": len(result.portfolio_snapshots)}
            if repeat:
                timings[name].append(elapsed)
            del result
    return {
        "bars": bars, "symbols": symbols, **counts,
        "engine_seconds": {name: median(values)
                           for name, values in timings.items()},
        "samples_seconds": timings,
        "result_sha256": expected_digest,
        "includes": "simulation, snapshots, metrics; excludes bundle I/O",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bars", type=int, default=4000)
    parser.add_argument("--symbols", type=int, default=3)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--lookup-only", action="store_true")
    parser.add_argument("--loop-inputs", action="store_true")
    parser.add_argument("--native-loop", action="store_true")
    arguments = parser.parse_args()
    if arguments.bars < 25 or arguments.symbols < 1 or arguments.repeats < 1:
        parser.error("Require bars >= 25, symbols >= 1 and repeats >= 1")
    if sum((arguments.loop_inputs, arguments.lookup_only,
            arguments.native_loop)) > 1:
        parser.error("Choose only one benchmark mode")
    output = {
        "python": platform.python_version(), "platform": platform.platform(),
        "pandas": pd.__version__,
    }
    if not arguments.loop_inputs and not arguments.native_loop:
        output["lookup"] = lookup_benchmark(arguments.bars, arguments.repeats)
    if not arguments.lookup_only:
        output["engine"] = engine_benchmark(
            arguments.bars, arguments.symbols, arguments.repeats,
            loop_inputs=arguments.loop_inputs,
            native_loop=arguments.native_loop,
        )
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
