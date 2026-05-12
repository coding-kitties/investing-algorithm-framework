"""Acceptance benchmark for epic #540 phase 2.

Generates a configurable number of synthetic ``.iafbt`` bundles
based on the test-suite fixture and measures:

* full index build time (``iaf index``)
* incremental re-index time (mtime/size skip path)
* query latency for ``iaf list --sort sharpe_ratio --limit 20``

Run with::

    source .venv/bin/activate
    python scripts/bench_540_phase2.py            # default: 1,000 bundles
    python scripts/bench_540_phase2.py --count 12500
"""

from __future__ import annotations

import argparse
import os
import shutil
import tempfile
import time
from pathlib import Path

from investing_algorithm_framework.domain import Backtest, BUNDLE_EXT
from investing_algorithm_framework.domain.backtesting.bundle import (
    save_bundle,
)
from investing_algorithm_framework.cli.index_command import (
    build_index, list_index,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (
    REPO_ROOT
    / "tests" / "resources" / "backtest_reports_for_testing"
    / "test_algorithm_backtest"
)


def _seed(out_dir: Path, n: int) -> None:
    """Write *n* bundles into *out_dir* by re-saving the template."""
    template = Backtest.open(str(TEMPLATE))
    base = template.to_dict()
    digits = max(5, len(str(n)))
    for i in range(n):
        bt = Backtest.from_dict(base)
        bt.algorithm_id = f"algo_{i:0{digits}d}"
        bt.tag = "bench"
        if bt.backtest_summary is not None:
            # Vary sharpe so sorting actually does work.
            bt.backtest_summary.sharpe_ratio = (i % 100) / 50.0 - 1.0
        save_bundle(
            bt, str(out_dir / f"{bt.algorithm_id}{BUNDLE_EXT}"),
        )


def _time(label: str, fn, *a, **kw):
    t0 = time.perf_counter()
    result = fn(*a, **kw)
    dt = time.perf_counter() - t0
    print(f"  {label:<40s} {dt * 1000:8.1f} ms")
    return result, dt


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=1000)
    ap.add_argument("--keep", action="store_true")
    args = ap.parse_args()

    work = Path(tempfile.mkdtemp(prefix="iaf-bench-540-"))
    print(f"Working directory: {work}")
    print(f"Seeding {args.count} .iafbt bundles...")
    t0 = time.perf_counter()
    _seed(work, args.count)
    print(f"  seeded in {time.perf_counter() - t0:.2f} s")

    print(f"\nBenchmark — {args.count} bundles")
    print("=" * 60)
    out, dt_build = _time(
        "build_index (cold)",
        build_index, str(work), show_progress=False,
    )
    _, dt_incr = _time(
        "build_index (incremental, all unchanged)",
        build_index, str(work), show_progress=False,
    )
    _, dt_list = _time(
        "list_index --sort sharpe_ratio --limit 20",
        list_index, str(work),
        sort_by="sharpe_ratio", limit=20,
    )
    _, dt_full = _time(
        "list_index --sort sharpe_ratio (no limit)",
        list_index, str(work), sort_by="sharpe_ratio",
    )

    index_path = work / "index.sqlite"
    size_mb = os.path.getsize(index_path) / (1024 * 1024)
    bundles_size = sum(
        p.stat().st_size for p in work.glob(f"*{BUNDLE_EXT}")
    ) / (1024 * 1024)
    print("\nFootprint")
    print("=" * 60)
    print(f"  bundle directory : {bundles_size:8.2f} MiB")
    print(f"  index.sqlite     : {size_mb:8.2f} MiB")
    print(f"  per-bundle index : {size_mb * 1024 / args.count:8.2f} KiB")

    print("\nProjection to 12,500 bundles (linear extrapolation)")
    print("=" * 60)
    scale = 12500 / args.count
    print(f"  build (cold)        : ~{dt_build * scale:.1f} s")
    print(f"  build (incremental) : ~{dt_incr * scale:.1f} s")
    print(
        f"  list top-20         :  {dt_list * 1000:.1f} ms "
        "(does not scale with bundle count)"
    )

    if not args.keep:
        shutil.rmtree(work, ignore_errors=True)
    else:
        print(f"\nLeft data in: {work}")


if __name__ == "__main__":
    main()
