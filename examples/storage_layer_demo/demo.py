"""End-to-end demo of the new tiered backtest storage layer.

Epic #540 phase 2:

* save a directory of ``.iafbt`` bundles
* build a SQLite Tier-1 index over them (``iaf index``)
* query / sort / filter the index (``iaf list`` / ``iaf rank``)
  without ever decoding the per-run Parquet metric blobs
* drop into raw SQL when needed

Run from the repo root::

    source .venv/bin/activate
    python examples/storage_layer_demo/demo.py
"""

from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

from investing_algorithm_framework.domain import Backtest, BUNDLE_EXT
from investing_algorithm_framework.domain.backtesting.bundle import (
    save_bundle,
)
from investing_algorithm_framework.cli.index_command import (
    build_index,
    list_index,
    rank_index,
    format_table,
)
from investing_algorithm_framework.services.backtest_store import (
    LocalDirStore,
)
from investing_algorithm_framework import BacktestReport


# Directory-format fixture shipped with the test suite. We use it
# only as a *template* — we re-save N copies under different
# algorithm_ids and Sharpe / Sortino / drawdown values so the demo
# has something interesting to rank.
REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE = (
    REPO_ROOT
    / "tests"
    / "resources"
    / "backtest_reports_for_testing"
    / "test_algorithm_backtest"
)


def _print_section(title: str) -> None:
    bar = "=" * 72
    print(f"\n{bar}\n {title}\n{bar}")


def _print_backtest_report(bt: Backtest) -> None:
    """Render a compact, fixture-tolerant report for a backtest.

    We deliberately read fields that exist on every ``.iafbt`` bundle
    (identity, run dates, summary metrics) instead of relying on the
    full :func:`pretty_print_backtest` helper, which assumes a
    populated :class:`BacktestMetrics` per run.
    """
    s = bt.backtest_summary
    runs = bt.backtest_runs or []
    print(f"  algorithm_id   : {bt.algorithm_id}")
    print(f"  tag            : {bt.tag}")
    if runs:
        first, last = runs[0], runs[-1]
        print(
            f"  date range     : {first.backtest_start_date} -> "
            f"{last.backtest_end_date}"
        )
        print(f"  number of runs : {len(runs)}")

    if s is None:
        print("  (no summary metrics available)")
        return

    def _row(label: str, value, fmt: str = "") -> None:
        if value is None:
            rendered = "n/a"
        elif fmt:
            rendered = format(value, fmt)
        else:
            rendered = str(value)
        print(f"  {label:<22}: {rendered}")

    print("  --- summary metrics ---")
    _row("sharpe_ratio", s.sharpe_ratio, ".4f")
    _row("sortino_ratio", s.sortino_ratio, ".4f")
    _row("calmar_ratio", s.calmar_ratio, ".4f")
    _row(
        "total_net_gain_pct",
        None if s.total_net_gain_percentage is None
        else s.total_net_gain_percentage * 100,
        ".2f",
    )
    _row(
        "max_drawdown_pct",
        None if s.max_drawdown is None else s.max_drawdown * 100,
        ".2f",
    )
    _row("number_of_trades", s.number_of_trades)
    _row(
        "win_rate_pct",
        None if s.win_rate is None else s.win_rate * 100,
        ".2f",
    )


def _print_backtest_full_report(bt: Backtest) -> None:
    """Render a detailed multi-section report for a single backtest.

    Goes beyond :func:`_print_backtest_report` by walking the
    per-run breakdown, listing positions, and showing the first few
    trades/orders so the demo's "open the winner" step actually
    looks like a backtest report and not just a summary row.
    """
    _print_backtest_report(bt)

    runs = bt.backtest_runs or []
    if not runs:
        return

    # ------------------- per-run breakdown -------------------
    print("\n  --- per-run breakdown ---")
    header = (
        f"  {'#':>2} {'window':<20} {'days':>5} {'orders':>7} "
        f"{'trades':>7} {'positions':>10} {'final_value':>14}"
    )
    print(header)
    print("  " + "-" * (len(header) - 2))
    for i, r in enumerate(runs, start=1):
        window = (
            r.backtest_date_range_name
            if r.backtest_date_range_name
            else f"{r.backtest_start_date.date()}..{r.backtest_end_date.date()}"
        )[:20]
        m = r.backtest_metrics
        final = (
            f"{float(m.final_value):.2f}"
            if m is not None and getattr(m, "final_value", None) is not None
            else "n/a"
        )
        print(
            f"  {i:>2} {window:<20} {r.number_of_days:>5} "
            f"{r.number_of_orders:>7} {r.number_of_trades:>7} "
            f"{r.number_of_positions:>10} {final:>14}"
        )

    # ------------------- positions snapshot -------------------
    last = runs[-1]
    positions = list(getattr(last, "positions", None) or [])
    if positions:
        print(f"\n  --- positions (last run, {len(positions)}) ---")
        for p in positions[:10]:
            symbol = getattr(p, "symbol", None) or "?"
            amount = getattr(p, "amount", None)
            cost = getattr(p, "cost", None)
            print(
                f"  {symbol:<14} amount={amount}  cost={cost}"
            )
        if len(positions) > 10:
            print(f"  ... and {len(positions) - 10} more")

    # ------------------- trades preview -------------------
    trades = list(getattr(last, "trades", None) or [])
    if trades:
        print(f"\n  --- trades (last run, {len(trades)} total, first 5) ---")
        for t in trades[:5]:
            print(
                f"  {getattr(t, 'symbol', '?'):<10} "
                f"opened={getattr(t, 'opened_at', None)} "
                f"net_gain={getattr(t, 'net_gain', None)}"
            )

    # ------------------- richer metrics from first run -------------------
    m = runs[0].backtest_metrics
    if m is None:
        return
    print("\n  --- additional risk / return metrics (first run) ---")
    extras = [
        ("cagr", "cagr", ".4f"),
        ("annual_volatility", "annual_volatility", ".4f"),
        ("max_drawdown_abs", "max_drawdown_absolute", ".2f"),
        ("max_drawdown_dur", "max_drawdown_duration", ""),
        ("gross_profit", "gross_profit", ".2f"),
        ("gross_loss", "gross_loss", ".2f"),
        ("best_trade", "best_trade", ".2f"),
        ("max_consec_wins", "max_consecutive_wins", ""),
        ("max_consec_losses", "max_consecutive_losses", ""),
    ]
    for label, attr, fmt in extras:
        val = getattr(m, attr, None)
        if val is None:
            rendered = "n/a"
        elif fmt:
            try:
                rendered = format(float(val), fmt)
            except (TypeError, ValueError):
                rendered = str(val)
        else:
            rendered = str(val)
        print(f"  {label:<22}: {rendered}")



def _seed_bundles(out_dir: Path, n: int = 6) -> None:
    """Write ``n`` synthetic ``.iafbt`` bundles into *out_dir*."""
    if not TEMPLATE.is_dir():
        sys.exit(
            f"Could not find the template fixture at {TEMPLATE}. "
            "Run this demo from inside a git checkout of the "
            "investing-algorithm-framework repository."
        )

    template = Backtest.open(str(TEMPLATE))

    # Three "strategy families", two variants each, with distinct
    # risk-adjusted profiles so ranking is meaningful.
    profiles = [
        ("momentum_v1", 1.85, 2.40, -0.08, 145, 0.61),
        ("momentum_v2", 1.42, 1.91, -0.12, 132, 0.58),
        ("mean_revert_v1", 0.95, 1.20, -0.18, 88, 0.54),
        ("mean_revert_v2", 1.10, 1.45, -0.15, 102, 0.55),
        ("breakout_v1", 0.42, 0.55, -0.31, 41, 0.48),
        ("breakout_v2", -0.20, -0.25, -0.42, 27, 0.39),
    ][:n]

    for algo_id, sharpe, sortino, mdd, n_trades, win_rate in profiles:
        bt = Backtest.from_dict(template.to_dict())
        bt.algorithm_id = algo_id
        bt.tag = "demo"
        if bt.backtest_summary is not None:
            s = bt.backtest_summary
            s.sharpe_ratio = sharpe
            s.sortino_ratio = sortino
            s.max_drawdown = mdd
            s.number_of_trades = n_trades
            s.win_rate = win_rate
            # Calmar = CAGR / |max_drawdown|; fake it for the demo.
            s.calmar_ratio = round(abs(sharpe / mdd), 3)
            s.total_net_gain_percentage = round(sharpe * 0.12, 4)
        save_bundle(
            bt, str(out_dir / f"{algo_id}{BUNDLE_EXT}"),
        )


def main() -> None:
    work = Path(tempfile.mkdtemp(prefix="iaf-storage-demo-"))
    print(f"Working directory: {work}")

    # ------------------------------------------------------------------
    # 1. Save bundles
    # ------------------------------------------------------------------
    _print_section("1. Save synthetic .iafbt bundles")
    _seed_bundles(work)
    for p in sorted(work.glob(f"*{BUNDLE_EXT}")):
        print(f"  {p.name}")

    # ------------------------------------------------------------------
    # 2. Build the Tier-1 SQLite index
    # ------------------------------------------------------------------
    _print_section("2. Build the SQLite Tier-1 index")
    print(f"$ iaf index {work}")
    index_path = build_index(str(work), show_progress=False)
    print(f"  -> wrote {index_path}")
    print(f"  -> file size: {os.path.getsize(index_path)} bytes")

    # ------------------------------------------------------------------
    # 3. iaf list — sort by Sharpe, top 4
    # ------------------------------------------------------------------
    _print_section("3. iaf list — sort by sharpe_ratio (top 4)")
    print(f"$ iaf list {work} --sort sharpe_ratio -n 4\n")
    rows = list_index(
        str(work), sort_by="sharpe_ratio", limit=4,
    )
    print(format_table(rows))

    # ------------------------------------------------------------------
    # 4. iaf rank — risk-adjusted, filtered
    # ------------------------------------------------------------------
    _print_section(
        "4. iaf rank — by sortino_ratio, with WHERE filter"
    )
    print(
        f'$ iaf rank {work} --by sortino_ratio '
        f'--where "summary_number_of_trades > 50" -n 5\n'
    )
    rows = rank_index(
        str(work),
        by="sortino_ratio",
        where="summary_number_of_trades > 50",
        limit=5,
    )
    print(format_table(rows))

    # ------------------------------------------------------------------
    # 5. Raw SQL — anything sqlite3 can do
    # ------------------------------------------------------------------
    _print_section("5. Raw SQL — custom report")
    sql = """
        SELECT algorithm_id,
               summary_sharpe_ratio   AS sharpe,
               summary_max_drawdown   AS max_dd,
               summary_calmar_ratio   AS calmar
          FROM backtest_index
         WHERE summary_max_drawdown > -0.20
         ORDER BY summary_calmar_ratio DESC
         LIMIT 5
    """
    print(f"$ sqlite3 {index_path} '<query>'\n{sql.strip()}\n")
    conn = sqlite3.connect(index_path)
    conn.row_factory = sqlite3.Row
    cur = conn.execute(sql)
    rows = [dict(r) for r in cur.fetchall()]
    conn.close()
    print(format_table(rows))

    # ------------------------------------------------------------------
    # 6. Open the winner's full backtest report
    # ------------------------------------------------------------------
    _print_section(
        "6. Open the top-ranked bundle and print its full report"
    )
    top = rank_index(str(work), by="sharpe_ratio", limit=1)[0]
    winner_path = work / top["bundle_path"]
    print(
        f"Top by sharpe_ratio: {top['algorithm_id']} "
        f"(sharpe={top['summary_sharpe_ratio']})\n"
        f"Loading full bundle: {winner_path}\n"
    )
    # The index gave us a scalar-only view; for the full report we
    # open the .iafbt bundle (this is the only step that decodes the
    # per-run Parquet metric blobs).
    winner_bt = Backtest.open(str(winner_path))
    _print_backtest_report(winner_bt)

    # ------------------------------------------------------------------
    # 6b. Full backtest report — per-run breakdown, positions, trades
    # ------------------------------------------------------------------
    _print_section(
        "6b. Full backtest report for the winner "
        "(runs / positions / trades)"
    )
    print(
        "Same bundle, expanded view: per-run breakdown, end-of-backtest "
        "positions, the first few trades, and a richer slice of "
        "per-run risk/return metrics.\n"
    )
    _print_backtest_full_report(winner_bt)

    # ------------------------------------------------------------------
    # 7. Iterate the index and print a one-line report per backtest
    # ------------------------------------------------------------------
    _print_section(
        "7. Iterate the index and print a one-line summary per bundle"
    )
    print(
        "Walking the SQLite index in rank order — no bundle is opened "
        "for these summaries.\n"
    )
    all_rows = list_index(str(work), sort_by="sharpe_ratio")
    for i, r in enumerate(all_rows, start=1):
        print(
            f"  {i}. {r['algorithm_id']:<14}  "
            f"sharpe={r['summary_sharpe_ratio']:>6.2f}  "
            f"return={r['summary_total_net_gain_percentage'] * 100:>6.2f}%  "
            f"max_dd={r['summary_max_drawdown']:>6.2%}  "
            f"trades={r['summary_number_of_trades']:>3}"
        )

    # ------------------------------------------------------------------
    # 8. Full report for every backtest in rank order
    # ------------------------------------------------------------------
    _print_section(
        "8. Full report per backtest (open each bundle in rank order)"
    )
    for i, r in enumerate(all_rows, start=1):
        bundle_path = work / r["bundle_path"]
        bt = Backtest.open(str(bundle_path))
        print(f"\n--- [{i}] {r['algorithm_id']} ".ljust(72, "-"))
        _print_backtest_report(bt)

    # ------------------------------------------------------------------
    # 9. Storage layer -> HTML dashboard
    # ------------------------------------------------------------------
    _print_section(
        "9. Storage layer -> HTML dashboard "
        "(rank in SQLite, load via store, render report)"
    )
    print(
        "Wire the Tier-1 SQLite index, the Tier-2 LocalDirStore and the\n"
        "BacktestReport HTML dashboard end-to-end:\n"
        "  1. rank_index() picks the top-N bundles from SQLite alone\n"
        "     (no Parquet metric blob is decoded yet).\n"
        "  2. LocalDirStore.open(handle) materialises just those\n"
        "     bundles through the BacktestStore protocol.\n"
        "  3. BacktestReport(backtests=[...]).save(path) renders the\n"
        "     interactive HTML dashboard with every loaded bundle.\n"
    )
    store = LocalDirStore(work)
    print(f"  store          : {type(store).__name__}({work})")
    print(f"  bundles in store: {len(store)}")

    top = rank_index(str(work), by="sharpe_ratio", limit=3)
    print(f"  top-3 by sharpe: {[r['algorithm_id'] for r in top]}")

    loaded: list[Backtest] = []
    for r in top:
        # The Tier-1 row's bundle_path is relative to the store root,
        # which is exactly what LocalDirStore uses as a handle.
        handle = r["bundle_path"]
        bt = store.open(handle)
        loaded.append(bt)
        print(
            f"    store.open({handle!r}) -> {bt.algorithm_id} "
            f"({len(bt.backtest_runs)} run(s))"
        )

    report = BacktestReport(backtests=loaded)
    html_path = work / "dashboard.html"
    report.save(str(html_path))
    html_size_kb = os.path.getsize(html_path) / 1024.0
    print(
        f"\n  wrote HTML dashboard -> {html_path}\n"
        f"  size: {html_size_kb:.1f} KB "
        f"(self-contained: CSS + JS + data inlined)\n"
        f"  open it with:  open {html_path}"
    )

    # ------------------------------------------------------------------
    # Wrap up
    # ------------------------------------------------------------------
    _print_section("Done")
    print(
        "Bundles + index + dashboard left in:\n"
        f"  {work}\n"
        "Try the CLI directly:\n"
        f"  iaf list {work} --sort calmar_ratio --json\n"
        f"  iaf rank {work} --by sharpe_ratio -n 3\n"
        f"  open {work / 'dashboard.html'}\n"
    )


if __name__ == "__main__":
    main()
