"""Compare full pandas/native calls, including conversion and result costs."""
import argparse
import json
import platform
from statistics import median
from time import perf_counter

import numpy as np
import pandas as pd

from investing_algorithm_framework import (
    AllOf, AnyOf, ConfluenceCard, Not, PrimaryGroup, Requirement, ScoreRule,
    Veto, condition,
)
from investing_algorithm_framework.domain.models.confluence_native import (
    _compile,
)


def workload(rows, rules):
    random = np.random.default_rng(42)
    frame = pd.DataFrame(random.normal(size=(rows, 4)),
                         columns=["price", "average", "momentum", "volume"])
    frame.iloc[::97, 2] = np.nan
    above = condition("price", "gt", reference="average")
    cross = condition("price", "cross_above", reference="average")
    positive = condition("momentum", "gt", value=0)
    card = ConfluenceCard(
        "native-benchmark", PrimaryGroup(AnyOf((above, cross))),
        scoring=tuple(ScoreRule(
            f"rule-{index}", AllOf((above, positive)), (index + 1) / 10
        ) for index in range(rules)),
        requirements=(Requirement("volume", condition(
            "volume", "between", value=(-3, 3)
        )),),
        vetoes=(Veto("negative", Not(AnyOf((above, positive)))),),
        minimum_score=1,
    )
    return card, frame


def benchmark(rows, rules, repeats):
    card, frame = workload(rows, rules)
    expected = card.evaluate_series(frame)
    _compile.cache_clear()
    started = perf_counter()
    actual = card.evaluate_series(frame, backend="rust")
    cold_seconds = perf_counter() - started
    pd.testing.assert_frame_equal(expected, actual, check_exact=True)
    samples = {"python": [], "rust": []}
    for repeat in range(repeats):
        backends = (
            ("python", "rust") if repeat % 2 == 0 else ("rust", "python")
        )
        for backend in backends:
            started = perf_counter()
            actual = card.evaluate_series(frame, backend=backend)
            samples[backend].append(perf_counter() - started)
            pd.testing.assert_frame_equal(expected, actual, check_exact=True)
    medians = {backend: median(values) for backend, values in samples.items()}
    return {
        "rows": rows, "rules": rules, "repeats": repeats,
        "cold_rust_seconds": cold_seconds, "samples_seconds": samples,
        "median_seconds": medians,
        "speedup": medians["python"] / medians["rust"],
        "exact_parity": True,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=int, default=100000)
    parser.add_argument("--rules", type=int, default=32)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if min(args.rows, args.rules, args.repeats) < 1:
        parser.error("rows, rules, and repeats must be positive")
    print(json.dumps({
        "platform": platform.platform(), "python": platform.python_version(),
        "pandas": pd.__version__, "numpy": np.__version__,
        "result": benchmark(args.rows, args.rules, args.repeats),
    }, indent=2))


if __name__ == "__main__":
    main()
