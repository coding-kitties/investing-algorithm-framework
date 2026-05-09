"""Render a side-by-side comparison table from the two result JSON files."""
from __future__ import annotations

import json
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"


def _load(name: str) -> dict | None:
    p = RESULTS / name
    if not p.exists():
        return None
    return json.loads(p.read_text())


def main() -> None:
    py = _load("python_bench.json")
    rs = _load("rust_bench.json")
    if py is None or rs is None:
        print("Missing results — run run_benchmark.sh first.")
        return

    rows = [
        ("implementation",                py["implementation"],                rs["implementation"]),
        ("persist (sqlite)",              "yes",                                "yes" if rs.get("persist") else "no"),
        ("metrics computed",              "yes",                                "yes" if rs.get("metrics") else "no"),
        ("backtests",                     py["n_backtests"],                   rs["n_backtests"]),
        ("symbols",                       py["n_symbols"],                     rs["n_symbols"]),
        ("years",                         py["years"],                         rs["years"]),
        ("workers",                       py["workers"],                       rs["workers"]),
        ("elapsed (s)",                   py["elapsed_seconds"],               rs["elapsed_seconds"]),
        ("backtests / s",                 py["throughput_backtests_per_second"], rs["throughput_backtests_per_second"]),
        ("ms / backtest",                 py["wall_clock_per_backtest_ms"],    rs["wall_clock_per_backtest_ms"]),
    ]
    width_metric = max(len(r[0]) for r in rows)
    width_py = max(len(str(r[1])) for r in rows + [("python_framework", "python", "")])
    width_rs = max(len(str(r[2])) for r in rows + [("rust_reference", "rust", "")])
    sep = "+" + "-" * (width_metric + 2) + "+" + "-" * (width_py + 2) + "+" + "-" * (width_rs + 2) + "+"
    print(sep)
    print(f"| {'metric'.ljust(width_metric)} | {'python_framework'.ljust(width_py)} | {'rust_reference'.ljust(width_rs)} |")
    print(sep)
    for name, p, r in rows:
        print(f"| {str(name).ljust(width_metric)} | {str(p).ljust(width_py)} | {str(r).ljust(width_rs)} |")
    print(sep)

    # Prefer the throughput ratio: it stays meaningful even when Rust
    # finishes in <1 ms (elapsed_seconds rounds to 0 in the JSON).
    throughput_ratio = (
        rs["throughput_backtests_per_second"]
        / py["throughput_backtests_per_second"]
        if py["throughput_backtests_per_second"]
        else 0.0
    )
    if rs["elapsed_seconds"] > 0:
        speedup = py["elapsed_seconds"] / rs["elapsed_seconds"]
    else:
        # Reconstruct from per-backtest wall-clock for tiny Rust runs.
        speedup = (
            py["wall_clock_per_backtest_ms"]
            / rs["wall_clock_per_backtest_ms"]
            if rs["wall_clock_per_backtest_ms"]
            else throughput_ratio
        )
    print()
    print(f"Wall-clock speedup (rust/python): {speedup:>10.1f}x")
    print(f"Throughput ratio   (rust/python): {throughput_ratio:>10.1f}x")
    print()
    print("This is the *ceiling* for a hypothetical iaf-core Rust kernel.")
    print("Both sides persist orders + portfolio snapshots to a per-backtest")
    print("SQLite DB *and* compute the standard metric pack (total return,")
    print("CAGR, vol, Sharpe, Sortino, max-DD + duration, Calmar). The Python")
    print("side additionally carries strategy lifecycle, data providers and")
    print("the full BacktestSummaryMetrics pipeline; the Rust side is a")
    print("minimal hand-rolled reference. The gap is the optimization")
    print("headroom for issues #521-#526.")


if __name__ == "__main__":
    main()
