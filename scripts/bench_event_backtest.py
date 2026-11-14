"""Profile complete offline event backtests through app.run_backtest.

Run from the repository root with ``python -m scripts.bench_event_backtest``.
Data and databases are temporary; no network requests or fixture writes.
"""
import argparse
from contextlib import ExitStack
import cProfile
import io
import json
import platform
import pstats
from statistics import median
import tempfile
from time import perf_counter
from unittest.mock import patch
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import event
from sqlalchemy.engine import Engine

from investing_algorithm_framework import (
    BacktestDateRange, BacktestEngine, BacktestRunConfiguration,
    BacktestWindow, CSVOHLCVDataProvider, RESOURCE_DIRECTORY, Study,
    Universe, create_app,
)
from investing_algorithm_framework.app.eventloop import EventLoopService
from investing_algorithm_framework.infrastructure.repositories.event_memory \
    import EventMemoryState
from investing_algorithm_framework.infrastructure.services.backtesting \
    .event_backtest_service import EventBacktestService
from scripts.bench_confluence_strategy import workload
from scripts.bench_vector_snapshot_events import result_digest, result_payload


def execute(rows, state_backend, profile=False, result_path=None):
    strategy, data = workload(rows + 40)
    raw = data["btc_2h"].copy()
    raw["Open"] = raw["Close"]
    raw["High"] = raw["Close"] * 1.001
    raw["Low"] = raw["Close"] * .999
    raw["Volume"] = 1000.
    strategy.algorithm_id = "confluence-event-benchmark"
    window = BacktestDateRange(
        start_date=raw.index[40].to_pydatetime(),
        end_date=raw.index[-1].to_pydatetime(),
    )
    phases = {}
    counters = {"ticks": 0, "tick_sql_statements": 0}
    inside_tick = False

    def count_statement(*args):
        if inside_tick:
            counters["tick_sql_statements"] += 1

    original_tick = EventLoopService._run_iteration
    original_close = EventMemoryState.close

    def measured_close(state):
        tables = {
            model.__name__: table for model, table in state.rows.items()
            if hasattr(table, "resident")
        }
        counters["resident_accounting_rows"] = {
            name: len(table.resident) for name, table in tables.items()
        }
        counters["archived_accounting_rows"] = {
            name: len(table) - len(table.resident)
            for name, table in tables.items()
        }
        return original_close(state)

    def measured_tick(loop, *args, **kwargs):
        nonlocal inside_tick
        inside_tick = True
        counters["ticks"] += 1
        try:
            return original_tick(loop, *args, **kwargs)
        finally:
            inside_tick = False

    def measure(name, method):
        def timed(*args, **kwargs):
            started = perf_counter()
            try:
                return method(*args, **kwargs)
            finally:
                phases[name] = (
                    phases.get(name, 0.) + perf_counter() - started
                )
        return timed

    with tempfile.TemporaryDirectory(prefix="iaf-event-bench-") as directory:
        csv = Path(directory) / "prices.csv"
        raw.rename_axis("Datetime").reset_index().to_csv(csv, index=False)
        app = create_app(config={RESOURCE_DIRECTORY: directory})
        app.add_market(
            market="BITVAVO", trading_symbol="EUR", initial_balance=10000,
        )
        app.add_data_provider(CSVOHLCVDataProvider(
            storage_path=str(csv), symbol="BTC/EUR", time_frame="2h",
            market="BITVAVO", warmup_window=40,
        ))
        profiler = cProfile.Profile() if profile else None
        with ExitStack() as stack:
            event.listen(Engine, "before_cursor_execute", count_statement)
            stack.callback(
                event.remove, Engine, "before_cursor_execute", count_statement,
            )
            stack.enter_context(patch.object(
                EventLoopService, "_run_iteration", measured_tick,
            ))
            stack.enter_context(patch.object(
                EventMemoryState, "close", measured_close,
            ))
            for cls, method, name in (
                (EventLoopService, "start", "event_loop"),
                (EventBacktestService, "prepare_indicators", "indicators"),
                (EventBacktestService, "_create_backtest_run", "results"),
            ):
                stack.enter_context(patch.object(
                    cls, method, measure(name, getattr(cls, method)),
                ))
            started = perf_counter()
            if profiler:
                profiler.enable()
            results = app.run_backtest(
                strategy=strategy,
                study=Study(
                    universe=Universe(
                        market="BITVAVO", trading_symbol="EUR",
                    ),
                    backtest_windows=[BacktestWindow(train_range=window)],
                    engines=[BacktestEngine.EVENT_DRIVEN],
                ),
                run_configuration=BacktestRunConfiguration(
                    show_progress=False, use_checkpoints=False,
                    continue_on_error=False, fill_missing_data=False,
                    event_state_backend=state_backend,
                ),
            )
            backtest = next(results.iter_backtests())
            run = backtest.event_runs[0]
            if profiler:
                profiler.disable()
            seconds = perf_counter() - started
        output = {
            "seconds": seconds, "phase_seconds": phases, **counters,
            "trades": len(run.trades), "orders": len(run.orders),
            "snapshots": len(run.portfolio_snapshots),
            "digest": result_digest(run),
        }
        if result_path is not None:
            Path(result_path).write_text(
                json.dumps(result_payload(run), indent=2), encoding="utf-8",
            )
        if profiler:
            text = io.StringIO()
            pstats.Stats(profiler, stream=text).sort_stats(
                "cumulative",
            ).print_stats(30)
            output["profile"] = text.getvalue()
        return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=1000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument(
        "--state-backend", choices=("sql", "memory"), default="sql",
    )
    parser.add_argument("--profile", action="store_true")
    parser.add_argument(
        "--result-json", type=Path,
        help="Save the first run's canonical results for exact comparisons.",
    )
    args = parser.parse_args()
    if min(args.rows, args.repeats) < 1:
        parser.error("rows and repeats must be positive")
    samples = [
        execute(
            args.rows, args.state_backend,
            result_path=args.result_json if index == 0 else None,
        )
        for index in range(args.repeats)
    ]
    assert len({sample["digest"] for sample in samples}) == 1
    output = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pandas": pd.__version__, "numpy": np.__version__,
        "rows": args.rows, "state_backend": args.state_backend,
        "sql_counter_scope": (
            "SQLAlchemy Engine statements; excludes private archive indexes"
        ),
        "median_seconds": median(sample["seconds"] for sample in samples),
        "samples": samples,
    }
    if args.profile:
        profiled = execute(args.rows, args.state_backend, profile=True)
        assert profiled["digest"] == samples[0]["digest"]
        output["profiled"] = profiled
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
