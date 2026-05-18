"""Backtest → flat-records decomposer for Tier-2 Parquet writes
(epic #540 phase 3b).

Given a :class:`Backtest`, yields flat record lists for each Tier-2
dataset (``portfolio_snapshots`` / ``trades`` / ``orders``). The
output is shaped for direct ingestion by
:func:`pyarrow.dataset.write_dataset` with hive partitioning on
``run_id``.

The bundle (``.iafbt``) remains the canonical source of truth in
Phase 3b; these Parquet datasets are *auxiliary* — they make
DuckDB / Polars analytics work across thousands of runs without
re-decoding bundles. Round-tripping Tier-2 back to a Backtest is
Phase 3d territory.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List

from investing_algorithm_framework.domain import Backtest


def _windowed_records(
    backtest: Backtest, attr: str, run_id: str,
) -> Iterator[Dict[str, Any]]:
    """Yield ``to_dict()``-shaped records from every BacktestRun.

    Adds ``run_id`` and ``window_name`` columns so downstream
    columnar tools can group / partition cleanly across a Backtest's
    walk-forward windows.
    """
    if not backtest.backtest_runs:
        return
    for window in backtest.backtest_runs:
        items = getattr(window, attr, None) or []
        window_name = getattr(window, "backtest_date_range_name", None) or (
            window.create_directory_name()
            if hasattr(window, "create_directory_name") else ""
        )
        for obj in items:
            d = obj.to_dict() if hasattr(obj, "to_dict") else dict(obj)
            d["run_id"] = run_id
            d["window_name"] = window_name
            yield d


def snapshots(backtest: Backtest, run_id: str) -> List[Dict[str, Any]]:
    """Flat portfolio_snapshots records, one per BacktestRun timestep."""
    return list(_windowed_records(backtest, "portfolio_snapshots", run_id))


def trades(backtest: Backtest, run_id: str) -> List[Dict[str, Any]]:
    """Flat trades records (one per trade across all windows)."""
    return list(_windowed_records(backtest, "trades", run_id))


def orders(backtest: Backtest, run_id: str) -> List[Dict[str, Any]]:
    """Flat orders records (one per order across all windows)."""
    return list(_windowed_records(backtest, "orders", run_id))


# Datasets exposed by LocalTieredStore. Each entry is
# (dataset_name, decomposer_fn). Add new kinds here (e.g.
# metric_series) once their decomposer is in place.
DATASETS = (
    ("portfolio_snapshots", snapshots),
    ("trades", trades),
    ("orders", orders),
)
