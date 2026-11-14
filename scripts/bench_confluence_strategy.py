"""Benchmark declarative vector preparation and prepared event decisions.

Run from the repository root:
    python -m scripts.bench_confluence_strategy
This measures signal generation, not broker execution or complete backtests.
"""
import argparse
import cProfile
import hashlib
import io
import json
import platform
import pstats
from statistics import median
from time import perf_counter
from types import SimpleNamespace

import numpy as np
import pandas as pd

from examples.framework_features.two_hour_confluence_strategy import (
    TwoHourConfluenceStrategy,
)
from investing_algorithm_framework.domain import INDEX_DATETIME


def workload(rows):
    offsets = np.arange(rows, dtype=float)
    close = 100 + offsets / 10000 + 4 * np.sin(offsets / 9)
    # Repeated discontinuities exercise all three oversold thresholds.
    close[::41] -= 8
    raw = pd.DataFrame(
        {"Close": close},
        index=pd.date_range(
            "2020-01-01", periods=rows, freq="2h", tz="UTC",
        ),
    )
    return TwoHourConfluenceStrategy(), {"btc_2h": raw}


def event_workload(strategy, data, ticks):
    engine = strategy.create_indicator_engine().prepare(data)
    strategy._indicator_engine = engine
    context = SimpleNamespace(
        config={}, get_open_trades=lambda **kwargs: [],
    )
    times = data["btc_2h"].index[-ticks:]

    def run():
        observations = []
        for timestamp in times:
            context.config[INDEX_DATETIME] = timestamp
            strategy._pending_decision_traces = []
            signals = list(strategy.generate_signals(context, {
                "indicators": engine.evaluate({}, timestamp),
            }))
            observations.append((
                [(signal.symbol, signal.side.value, signal.source,
                  dict(signal.metadata)) for signal in signals],
                strategy._pending_decision_traces,
            ))
        return observations

    return run


def benchmark(rows, ticks, repeats, profile=False):
    strategy, data = workload(rows)
    expected_masks = list(strategy.generate_signal_series(data))
    expected_events = event_workload(strategy, data, ticks)()
    samples = {"vector_prepare": [], "prepared_events": []}
    profile_text = {}

    def run_vector():
        return list(strategy.generate_signal_series(data))

    for mode in samples:
        for repeat in range(repeats):
            if mode == "vector_prepare":
                run = run_vector
            else:
                # Build prepared state outside the event timing.
                run = event_workload(strategy, data, ticks)
            started = perf_counter()
            actual = run()
            samples[mode].append(perf_counter() - started)
            if mode == "vector_prepare":
                assert len(actual) == len(expected_masks)
                for expected, mask in zip(expected_masks, actual):
                    assert (mask.symbol, mask.side, mask.metadata) == (
                        expected.symbol, expected.side, expected.metadata,
                    )
                    pd.testing.assert_series_equal(
                        expected.series, mask.series,
                    )
            else:
                assert actual == expected_events
        if profile:
            if mode == "prepared_events":
                run = event_workload(strategy, data, ticks)
            profiler = cProfile.Profile()
            profiler.runcall(run)
            output = io.StringIO()
            pstats.Stats(profiler, stream=output).sort_stats(
                "cumulative",
            ).print_stats(18)
            profile_text[mode] = output.getvalue()
    mask_digest = hashlib.sha256()
    for mask in expected_masks:
        mask_digest.update(json.dumps((
            mask.symbol, mask.side.value, mask.source, dict(mask.metadata),
        ), sort_keys=True).encode())
        mask_digest.update(mask.series.index.asi8.tobytes())
        mask_digest.update(mask.series.to_numpy(dtype=bool).tobytes())
    return {
        "rows": rows, "event_ticks": ticks, "repeats": repeats,
        "samples_seconds": samples,
        "median_seconds": {
            mode: median(values) for mode, values in samples.items()
        },
        "exact_repeat_parity": True,
        "mask_digest": mask_digest.hexdigest(),
        "event_digest": hashlib.sha256(json.dumps(
            expected_events, sort_keys=True, allow_nan=False,
        ).encode()).hexdigest(),
        "profiles": profile_text,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=50000)
    parser.add_argument("--ticks", type=int, default=500)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--profile", action="store_true")
    args = parser.parse_args()
    if min(args.rows, args.ticks, args.repeats) < 1:
        parser.error("rows, ticks, and repeats must be positive")
    if args.ticks > args.rows:
        parser.error("ticks cannot exceed rows")
    print(json.dumps({
        "python": platform.python_version(),
        "platform": platform.platform(),
        "pandas": pd.__version__, "numpy": np.__version__,
        "result": benchmark(
            args.rows, args.ticks, args.repeats, args.profile,
        ),
    }, indent=2))


if __name__ == "__main__":
    main()
