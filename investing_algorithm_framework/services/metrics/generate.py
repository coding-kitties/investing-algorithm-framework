from typing import List, Optional, Union
from logging import getLogger
import gc
import os
import sys
import warnings
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED

from investing_algorithm_framework.domain import BacktestMetrics, \
    BacktestRun, OperationalException, Backtest, BacktestDateRange
from investing_algorithm_framework.domain.backtesting.combine_backtests \
    import generate_backtest_summary_metrics
from .cagr import get_cagr
from .calmar_ratio import get_calmar_ratio
from .drawdown import get_drawdown_series, get_max_drawdown, \
    get_max_daily_drawdown, get_max_drawdown_absolute, \
    get_max_drawdown_duration, \
    get_twr_drawdown_series, get_twr_max_drawdown, \
    get_twr_max_drawdown_duration
from .equity_curve import get_equity_curve, get_twr_equity_curve
from .exposure import get_exposure_ratio, get_cumulative_exposure, \
    get_trades_per_year, get_trades_per_day, get_trades_per_week, \
    get_trades_per_month
from .profit_factor import get_profit_factor, get_gross_loss, get_gross_profit
from .returns import get_monthly_returns, get_yearly_returns, \
    get_worst_year, get_best_year, get_best_month, get_worst_month, \
    get_percentage_winning_months, get_percentage_winning_years, \
    get_average_monthly_return, get_average_monthly_return_winning_months, \
    get_average_monthly_return_losing_months, get_cumulative_return, \
    get_cumulative_return_series
from .returns import get_total_return, get_final_value, \
    get_total_growth
from .sharpe_ratio import get_sharpe_ratio, get_rolling_sharpe_ratio
from .sortino_ratio import get_sortino_ratio
from .omega_ratio import get_omega_ratio
from .ulcer import get_ulcer_index
from .mae_mfe import get_trade_mae_mfe_statistics
from .volatility import get_annual_volatility
from .win_rate import get_win_rate, get_win_loss_ratio, get_current_win_rate, \
    get_current_win_loss_ratio
from .trades import get_average_trade_duration, get_average_trade_size, \
    get_number_of_trades, get_positive_trades, get_number_of_closed_trades, \
    get_negative_trades, get_average_trade_return, get_number_of_open_trades, \
    get_worst_trade, get_best_trade, get_average_trade_gain, \
    get_average_trade_loss, get_median_trade_return, \
    get_current_average_trade_gain, get_current_average_trade_return, \
    get_current_average_trade_duration, get_current_average_trade_loss, \
    get_average_win_duration, get_average_loss_duration, \
    get_max_consecutive_wins, get_max_consecutive_losses, \
    get_directional_trade_statistics
from .value_at_risk import get_value_at_risk, \
    get_conditional_value_at_risk

logger = getLogger("investing_algorithm_framework")

def create_backtest_metrics_for_backtest(
    backtest: Backtest,
    risk_free_rate: float, metrics: List[str] = None,
    backtest_date_range: BacktestDateRange = None
) -> Backtest:

    """
    Create BacktestMetrics for a Backtest object.

    Args:
        backtest (Backtest): The Backtest object containing
            backtest runs.
        risk_free_rate (float): The risk-free rate used in certain
            metric calculations.
        metrics (List[str], optional): List of metric names to compute.
            If None, a default set of metrics will be computed.
        backtest_date_range (BacktestDateRange, optional): The date range
            for the backtest. If None, all backtest metrics will be computed
            for each backtest run.

    Returns:
        Backtest: The Backtest object with computed metrics for each run.
    """
    if backtest_date_range is not None:
        backtest_runs = [
            backtest.get_backtest_run(backtest_date_range)
        ]
    else:
        backtest_runs = backtest.get_all_backtest_runs()

    for backtest_run in backtest_runs:
        # If a date range is provided, check if the backtest run falls
        # within the range
        backtest_metrics = create_backtest_metrics(
            backtest_run, risk_free_rate, metrics
        )
        backtest_run.backtest_metrics = backtest_metrics

    # ``backtest_runs`` above is the concatenated view returned by
    # ``get_all_backtest_runs()``; the BacktestRun instances are the
    # same objects already held in ``backtest.vector_runs`` /
    # ``backtest.event_runs``, so mutating their ``backtest_metrics``
    # in place is all that's needed. The v8 assignment
    # ``backtest.backtest_runs = backtest_runs`` is no longer required
    # — the engine slot lists are already up to date.
    return backtest


def _recalculate_one(args):
    """Process-pool worker for :func:`recalculate_backtests`.

    Must be a module-level function so it pickles. Returns only the
    freshly computed per-run metrics and summary so the parent can
    merge them into the existing backtest object without round-tripping
    the full snapshots/trades back through pickle.
    """
    backtest, risk_free_rate, metrics = args
    _st = backtest._get_default_study()
    _study_rfr = _st.risk_free_rate if _st is not None else None
    rfr = risk_free_rate if risk_free_rate is not None \
        else (_study_rfr or 0.0)

    run_metrics = [
        create_backtest_metrics(run, rfr, metrics)
        for run in backtest.get_all_backtest_runs()
    ]
    summary = generate_backtest_summary_metrics(
        [m for m in run_metrics if m is not None]
    )
    # Drop the local Backtest reference and force a collection so the
    # worker's RSS can shrink between tasks. Without this the heap can
    # grow unboundedly when one worker handles many large backtests.
    del backtest
    gc.collect()
    return run_metrics, summary


def _recalculate_one_path(args):
    """Worker entry: load a backtest from disk, recalc all metrics,
    save it back to disk, return the path and a flat index row.

    Used by :func:`recalculate_backtests_in_directory`. The Backtest
    never crosses the process boundary so the parent stays flat,
    regardless of batch size.

    *args* is a dict with the following keys:

    * ``src_path`` / ``dst_path``: input / output bundle paths.
    * ``risk_free_rate`` / ``metrics``: forwarded to
      :func:`create_backtest_metrics`.
    * ``include_ohlcv`` / ``ohlcv_store``: forwarded to
      :func:`save_bundle`.
    * ``study`` (optional): only recompute runs for this study slot.
      Both the legacy/default-study slot and all other studies
      are considered.
    * ``engine`` (optional): one of ``"vector"`` / ``"event"``;
      restricts recomputation to that engine.
    * ``windows`` (optional): list of :class:`BacktestDateRange`
      objects; only runs whose ``(backtest_start_date,
      backtest_end_date)`` matches one of these are recomputed.
    """
    src_path = args["src_path"]
    dst_path = args["dst_path"]
    risk_free_rate = args.get("risk_free_rate")
    metrics = args.get("metrics")
    include_ohlcv = args.get("include_ohlcv", False)
    ohlcv_store = args.get("ohlcv_store")
    study_filter = args.get("study")
    engine_filter = args.get("engine")
    windows = args.get("windows")

    # Local imports keep the worker startup cost predictable and avoid
    # circular-import issues at module load time.
    from investing_algorithm_framework.domain.backtesting.bundle import (
        is_bundle_file, open_bundle, save_bundle,
    )
    from investing_algorithm_framework.domain.backtesting.backtest \
        import Backtest as _Backtest, ENGINES, ENGINE_VECTOR
    from investing_algorithm_framework.domain.backtesting.backtest_utils \
        import _backtest_to_index_rows

    bt = open_bundle(src_path) if is_bundle_file(src_path) \
        else _Backtest.open(src_path)
    _bt_st = bt._get_default_study()
    _bt_rfr = _bt_st.risk_free_rate if _bt_st is not None else None
    rfr = risk_free_rate if risk_free_rate is not None \
        else (_bt_rfr or 0.0)

    # Build the list of runs to recompute, honouring the optional
    # study/engine/windows filters across all studies.
    targets = []  # list of BacktestRun objects to recompute
    for name, study in bt.studies.items():
        if study_filter is not None and study_filter != name:
            continue
        for engine_name, slot in study.engines.items():
            if engine_filter is not None and engine_filter != engine_name:
                continue
            targets.extend(slot.runs)

    if windows:
        wanted = {(w.start_date, w.end_date) for w in windows}
        targets = [
            r for r in targets
            if (r.backtest_start_date, r.backtest_end_date) in wanted
        ]

    for run in targets:
        run.backtest_metrics = create_backtest_metrics(run, rfr, metrics)

    # v9.0: each engine has its own summary; ``regenerate_summaries``
    # rebuilds all study slots from the newly populated per-run
    # metrics so the persisted bundle stays self-consistent.
    bt.regenerate_summaries()

    out = str(save_bundle(
        bt, dst_path,
        include_ohlcv=include_ohlcv,
        ohlcv_store=ohlcv_store,
    ))
    rows = _backtest_to_index_rows(bt, bundle_path=os.path.basename(out))
    del bt
    gc.collect()
    return out, rows


def _apply_recalc_result(backtest, run_metrics, summary):
    runs = backtest.get_all_backtest_runs()
    for run, bm in zip(runs, run_metrics):
        run.backtest_metrics = bm
    # ``summary`` (the cross-engine roll-up computed by the worker) is
    # intentionally ignored. v9.0 stores summaries per engine; we
    # regenerate them from the freshly assigned per-run metrics so
    # vector and event summaries stay independent and self-consistent.
    del summary
    backtest.regenerate_summaries()


def _make_pool(n_workers: int, max_tasks_per_child: Optional[int]):
    """Create a :class:`ProcessPoolExecutor`, opting into
    ``max_tasks_per_child`` on Python 3.11+ where it is supported.

    Worker recycling is essential for memory-stable long runs because
    each task can leave behind cached pandas/polars / numpy buffers
    that the worker's allocator never returns to the OS. Recycling
    after a fixed number of tasks reclaims that memory.
    """
    if (
        max_tasks_per_child is not None
        and sys.version_info >= (3, 11)
    ):
        return ProcessPoolExecutor(
            max_workers=n_workers,
            max_tasks_per_child=max_tasks_per_child,
        )
    return ProcessPoolExecutor(max_workers=n_workers)


def _run_pool(
    submit_fn,
    items,
    n_workers: int,
    max_tasks_per_child: Optional[int],
    on_result,
    on_error=None,
):
    """Run ``submit_fn(item)`` over *items* with at most ``n_workers``
    tasks in flight.

    On Python < 3.11, where ``max_tasks_per_child`` does not exist on
    :class:`ProcessPoolExecutor`, we emulate worker recycling by
    closing and re-opening the executor every
    ``max_tasks_per_child * n_workers`` completions. This keeps RSS
    flat at the cost of process startup overhead between batches.
    """
    has_native_recycle = (
        max_tasks_per_child is not None
        and sys.version_info >= (3, 11)
    )

    items_iter = iter(items)
    completed_in_pool = 0
    pool_capacity = (
        (max_tasks_per_child or 0) * n_workers
        if max_tasks_per_child and not has_native_recycle else None
    )

    def _open():
        return _make_pool(n_workers, max_tasks_per_child)

    ex = _open()
    inflight = {}

    def _submit_next():
        nonlocal ex, completed_in_pool, inflight
        try:
            item = next(items_iter)
        except StopIteration:
            return False
        fut = ex.submit(submit_fn, item)
        inflight[fut] = item
        return True

    try:
        for _ in range(n_workers):
            if not _submit_next():
                break

        while inflight:
            done_set, _unused = wait(
                inflight.keys(), return_when=FIRST_COMPLETED
            )
            for fut in done_set:
                item = inflight.pop(fut)
                try:
                    on_result(item, fut.result())
                except Exception as e:
                    if on_error is not None:
                        on_error(item, e)
                    else:
                        logger.error(f"Task failed: {e}")
                completed_in_pool += 1

            # Emulated recycling: drain the pool, recreate it.
            if (
                pool_capacity is not None
                and completed_in_pool >= pool_capacity
                and not inflight
            ):
                ex.shutdown(wait=True)
                ex = _open()
                completed_in_pool = 0
                for _ in range(n_workers):
                    if not _submit_next():
                        break
            else:
                _submit_next()
    finally:
        ex.shutdown(wait=True)


def recalculate_backtests(
    backtests: List[Backtest],
    risk_free_rate: float = None,
    metrics: List[str] = None,
    workers: Optional[int] = None,
    max_tasks_per_child: Optional[int] = 16,
) -> List[Backtest]:
    """Recalculate all metrics for a set of in-memory backtests.

    Args:
        backtests: The backtests to recalculate (mutated in place).
        risk_free_rate: Risk-free rate to use. If ``None``, uses each
            backtest's own ``risk_free_rate`` (falling back to ``0.0``).
        metrics: Metric names to compute. ``None`` uses the default set.
        workers: Number of parallel worker processes. ``None`` or
            ``1`` runs serially in the calling process.
        max_tasks_per_child: Recycle each worker after this many tasks
            to keep RSS flat. Set to ``None`` to disable recycling.

    Returns:
        The same backtest objects, mutated in place.
    """
    if not backtests:
        return backtests

    n_workers = max(1, int(workers)) if workers is not None else 1

    if n_workers <= 1 or len(backtests) <= 1:
        for backtest in backtests:
            run_metrics, summary = _recalculate_one(
                (backtest, risk_free_rate, metrics)
            )
            _apply_recalc_result(backtest, run_metrics, summary)
        return backtests

    index_by_id = {id(bt): i for i, bt in enumerate(backtests)}
    items = (
        (bt, risk_free_rate, metrics) for bt in backtests
    )

    def _on_result(item, result):
        bt = item[0]
        run_metrics, summary = result
        _apply_recalc_result(backtests[index_by_id[id(bt)]],
                             run_metrics, summary)

    def _on_error(item, exc):
        bt = item[0]
        logger.error(
            "Failed to recalculate backtest "
            f"{getattr(bt, 'algorithm_id', '?')}: {exc}"
        )

    _run_pool(
        _recalculate_one,
        items,
        n_workers=n_workers,
        max_tasks_per_child=max_tasks_per_child,
        on_result=_on_result,
        on_error=_on_error,
    )
    return backtests


def recalculate_backtests_in_directory(
    src_dir: Union[str, Path],
    dst_dir: Optional[Union[str, Path]] = None,
    *,
    risk_free_rate: float = None,
    metrics: List[str] = None,
    workers: Optional[int] = None,
    show_progress: bool = False,
    include_ohlcv: bool = False,
    max_tasks_per_child: Optional[int] = 16,
    update_index: bool = True,
    study: Optional[str] = None,
    engine: Optional[str] = None,
    windows: Optional[List[BacktestDateRange]] = None,
) -> int:
    """Stream-recalculate backtest metrics for every bundle on disk.

    Each backtest is loaded, recalculated, and written back **inside a
    worker process**. The full :class:`Backtest` never crosses the
    process boundary, so the parent process's memory footprint stays
    constant regardless of how many backtests are processed.

    Args:
        src_dir: Directory containing ``.obtf`` bundles (and/or
            legacy backtest directories).
        dst_dir: Output directory. If ``None``, bundles are rewritten
            in place inside *src_dir*.
        risk_free_rate: Risk-free rate to use. ``None`` uses each
            backtest's own ``risk_free_rate``.
        metrics: Metric names to compute. ``None`` uses the default
            set.
        workers: Number of parallel worker processes. Defaults to
            ``min(8, cpu_count)``. Pass ``1`` to force serial.
        show_progress: Display a tqdm progress bar.
        include_ohlcv: Re-emit attached OHLCV data with the bundle.
        max_tasks_per_child: Recycle each worker after this many tasks
            so RSS stays bounded over long runs.
        update_index: Rewrite ``index.parquet`` in *dst_dir* (or
            *src_dir* when in-place) using the freshly computed
            summaries.
        study: Optional study name. When provided, only runs belonging
            to that study slot are recomputed; all other studies on
            the bundle keep their existing per-run metrics. All
            studies are honoured. Per-engine
            summaries are still regenerated for *every* slot so
            cross-study aggregates stay consistent with the latest
            per-run metrics.
        engine: Optional engine filter (``"vector"`` or ``"event"``);
            restricts recomputation to that engine.
        windows: Optional list of :class:`BacktestDateRange` objects;
            only runs whose ``(start_date, end_date)`` matches one of
            these are recomputed.

    Returns:
        Number of backtests recalculated.
    """
    from investing_algorithm_framework.domain.backtesting.bundle \
        import BUNDLE_EXT
    from investing_algorithm_framework.domain.backtesting.backtest \
        import ENGINES
    from investing_algorithm_framework.domain.backtesting.backtest_utils \
        import _resolve_workers
    from investing_algorithm_framework.domain.utils.custom_tqdm import tqdm

    if engine is not None and engine not in ENGINES:
        raise OperationalException(
            f"Unknown engine {engine!r}, expected one of {list(ENGINES)}."
        )

    src_dir = Path(src_dir)
    in_place = dst_dir is None
    out_dir = src_dir if in_place else Path(dst_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Discover sources without loading them.
    sources: List[str] = []
    for root, dirs, files in os.walk(src_dir):
        for fname in files:
            if fname.endswith(BUNDLE_EXT):
                sources.append(os.path.join(root, fname))
        for dname in list(dirs):
            d = os.path.join(root, dname)
            if (
                os.path.isfile(os.path.join(d, "algorithm_id.json"))
                and os.path.isdir(os.path.join(d, "runs"))
            ):
                sources.append(d)
                dirs.remove(dname)

    if not sources:
        return 0

    ohlcv_store = (
        str(out_dir / "ohlcv") if include_ohlcv else None
    )

    plan = []
    for src in sources:
        base = os.path.basename(os.path.normpath(src))
        if base.endswith(BUNDLE_EXT):
            base = base[: -len(BUNDLE_EXT)]
        dst = str(out_dir / f"{base}{BUNDLE_EXT}")
        plan.append({
            "src_path": src,
            "dst_path": dst,
            "risk_free_rate": risk_free_rate,
            "metrics": metrics,
            "include_ohlcv": include_ohlcv,
            "ohlcv_store": ohlcv_store,
            "study": study,
            "engine": engine,
            "windows": windows,
        })

    n = len(plan)
    n_workers = min(_resolve_workers(workers), n)

    pbar = tqdm(
        total=n,
        desc="Recalculating backtests",
        disable=not show_progress,
    )

    rows: List[dict] = []

    def _on_result(item, result):
        # ``_recalculate_one_path`` now returns ``(out_path, rows)``
        # where ``rows`` is a list with one entry per populated engine
        # (v9.0). Extend the index accumulator with all returned rows.
        out_path, new_rows = result
        if update_index and new_rows:
            rows.extend(new_rows)
        pbar.update(1)

    def _on_error(item, exc):
        logger.error(f"Failed to recalculate {item['src_path']}: {exc}")
        pbar.update(1)

    try:
        if n_workers <= 1:
            for item in plan:
                try:
                    result = _recalculate_one_path(item)
                    _on_result(item, result)
                except Exception as e:
                    _on_error(item, e)
        else:
            _run_pool(
                _recalculate_one_path,
                plan,
                n_workers=n_workers,
                max_tasks_per_child=max_tasks_per_child,
                on_result=_on_result,
                on_error=_on_error,
            )
    finally:
        pbar.close()

    if update_index and rows:
        import pandas as pd  # local import keeps top of module light
        df = pd.DataFrame(rows)
        df.to_parquet(
            out_dir / "index.parquet",
            index=False,
            compression="zstd",
        )

    return n


def create_backtest_metrics(
    backtest_run: BacktestRun,
    risk_free_rate: float,
    metrics: List[str] = None,
) -> BacktestMetrics:
    """
    Create a BacktestMetrics instance and optionally save it to a file.

    Args:
        backtest_run (BacktestRun): The BacktestRun object containing
            portfolio snapshots and trades.
        risk_free_rate (float): The risk-free rate used in certain
            metric calculations.
        metrics (List[str], optional): List of metric names to compute.
            If None, a default set of metrics will be computed.
    Returns:
        BacktestMetrics: The computed backtest metrics.
    """

    if metrics is None:
        metrics = [
            "backtest_start_date",
            "backtest_end_date",
            "equity_curve",
            "final_value",
            "total_growth",
            "total_growth_percentage",
            "total_net_gain",
            "total_net_gain_percentage",
            "total_loss",
            "total_loss_percentage",
            "cumulative_return",
            "cumulative_return_series",
            "cagr",
            "sharpe_ratio",
            "rolling_sharpe_ratio",
            "sortino_ratio",
            "calmar_ratio",
            "omega_ratio",
            "profit_factor",
            "annual_volatility",
            "ulcer_index",
            "monthly_returns",
            "yearly_returns",
            "drawdown_series",
            "max_drawdown",
            "max_drawdown_absolute",
            "max_daily_drawdown",
            "max_drawdown_duration",
            "twr_equity_curve",
            "twr_drawdown_series",
            "twr_max_drawdown",
            "twr_max_drawdown_duration",
            "trades_per_year",
            "trades_per_week",
            "trades_per_month",
            "trade_per_day",
            "exposure_ratio",
            "cumulative_exposure",
            "best_trade",
            "worst_trade",
            "number_of_positive_trades",
            "percentage_positive_trades",
            "number_of_negative_trades",
            "percentage_negative_trades",
            "average_trade_duration",
            "average_win_duration",
            "average_loss_duration",
            "average_trade_size",
            "average_trade_loss",
            "average_trade_loss_percentage",
            "average_trade_gain",
            "average_trade_gain_percentage",
            "average_trade_return",
            "average_trade_return_percentage",
            "average_mae",
            "average_mae_percentage",
            "average_mfe",
            "average_mfe_percentage",
            "max_mae",
            "max_mfe",
            "mfe_mae_ratio",
            "median_trade_return",
            "number_of_trades",
            "number_of_trades_closed",
            "number_of_trades_opened",
            "number_of_trades_open_at_end",
            "number_of_long_trades",
            "number_of_long_trades_closed",
            "number_of_winning_long_trades",
            "number_of_losing_long_trades",
            "long_win_rate",
            "number_of_short_trades",
            "number_of_short_trades_closed",
            "number_of_winning_short_trades",
            "number_of_losing_short_trades",
            "short_win_rate",
            "win_rate",
            "current_win_rate",
            "win_loss_ratio",
            "current_win_loss_ratio",
            "percentage_winning_months",
            "percentage_winning_years",
            "average_monthly_return",
            "average_monthly_return_losing_months",
            "average_monthly_return_winning_months",
            "best_month",
            "best_year",
            "worst_month",
            "worst_year",
            "total_number_of_days",
            "current_average_trade_gain",
            "current_average_trade_return",
            "current_average_trade_duration",
            "current_average_trade_loss",
            "var_95",
            "cvar_95",
            "max_consecutive_wins",
            "max_consecutive_losses",
            "gross_profit",
            "gross_loss",
        ]

    backtest_metrics = BacktestMetrics(
        backtest_window=backtest_run.backtest_window,
        initial_unallocated=backtest_run.initial_unallocated or 0.0,
    )

    def safe_set(metric_name, func, *args, index=None):
        if metric_name in metrics:
            try:
                value = func(*args)
                if index is not None and isinstance(value, (list, tuple)):
                    setattr(backtest_metrics, metric_name, value[index])
                else:
                    setattr(backtest_metrics, metric_name, value)
            except OperationalException as e:
                logger.warning(f"{metric_name} failed: {e}")

    # Grouped metrics needing special handling
    if "total_net_gain" in metrics or "total_net_gain_percentage" in metrics:
        try:
            total_return = get_total_return(backtest_run.portfolio_snapshots)
            if "total_net_gain" in metrics:
                backtest_metrics.total_net_gain = total_return[0]
            if "total_net_gain_percentage" in metrics:
                backtest_metrics.total_net_gain_percentage = total_return[1]
        except OperationalException as e:
            logger.warning(f"total_return failed: {e}")

    if "total_growth" in metrics or "total_growth_percentage" in metrics:
        try:
            total_growth = get_total_growth(backtest_run.portfolio_snapshots)
            if "total_growth" in metrics:
                backtest_metrics.total_growth = total_growth[0]
            if "total_growth_percentage" in metrics:
                backtest_metrics.total_growth_percentage = total_growth[1]
        except OperationalException as e:
            logger.warning(f"total_growth failed: {e}")

    if "total_loss" in metrics or "total_loss_percentage" in metrics:
        try:
            # B1 fix (issue #511): "total_loss" is now the **gross loss**
            # (sum of P&L of all losing trades, expressed as a non-negative
            # magnitude) rather than the snapshot net-return clamped at
            # zero. The latter was indistinguishable from
            # ``total_net_gain`` whenever the period was unprofitable and
            # always 0 otherwise. ``total_loss_percentage`` is the gross
            # loss expressed as a fraction of the initial unallocated
            # capital (decimal, e.g. ``0.05`` for a 5% loss magnitude).
            gross_loss_value = get_gross_loss(backtest_run.trades)
            initial_value = backtest_run.initial_unallocated or 0.0

            if "total_loss" in metrics:
                backtest_metrics.total_loss = gross_loss_value
            if "total_loss_percentage" in metrics:
                if initial_value > 0:
                    backtest_metrics.total_loss_percentage = (
                        gross_loss_value / initial_value
                    )
                else:
                    backtest_metrics.total_loss_percentage = 0.0
        except OperationalException as e:
            logger.warning(f"total_loss failed: {e}")

    if ("average_trade_return" in metrics
            or "average_trade_return_percentage" in metrics):
        try:
            avg_return = get_average_trade_return(backtest_run.trades)
            if "average_trade_return" in metrics:
                backtest_metrics.average_trade_return = avg_return[0]
            if "average_trade_return_percentage" in metrics:
                backtest_metrics.average_trade_return_percentage = \
                    avg_return[1]
        except OperationalException as e:
            logger.warning(f"average_trade_return failed: {e}")

    if ("average_trade_gain" in metrics
            or "average_trade_gain_percentage" in metrics):
        try:
            avg_gain = get_average_trade_gain(backtest_run.trades)
            if "average_trade_gain" in metrics:
                backtest_metrics.average_trade_gain = avg_gain[0]
            if "average_trade_gain_percentage" in metrics:
                backtest_metrics.average_trade_gain_percentage = avg_gain[1]
        except OperationalException as e:
            logger.warning(f"average_trade_gain failed: {e}")

    if ("average_trade_loss" in metrics
            or "average_trade_loss_percentage" in metrics):
        try:
            avg_loss = get_average_trade_loss(backtest_run.trades)
            if "average_trade_loss" in metrics:
                backtest_metrics.average_trade_loss = avg_loss[0]
            if "average_trade_loss_percentage" in metrics:
                backtest_metrics.average_trade_loss_percentage = avg_loss[1]
        except OperationalException as e:
            logger.warning(f"average_trade_loss failed: {e}")

    if ("current_average_trade_gain" in metrics
            or "get_current_average_trade_gain_percentage" in metrics):
        try:
            current_avg_gain = get_current_average_trade_gain(
                backtest_run.trades
            )

            if "current_average_trade_gain" in metrics:
                backtest_metrics.current_average_trade_gain = \
                    current_avg_gain[0]

            if "current_average_trade_gain_percentage" in metrics:
                backtest_metrics.current_average_trade_gain_percentage = \
                    current_avg_gain[1]
        except OperationalException as e:
            logger.warning(f"current_average_trade_gain failed: {e}")

    if ("current_average_trade_return" in metrics
            or "current_average_trade_return_percentage" in metrics):
        try:
            current_avg_return = get_current_average_trade_return(
                backtest_run.trades
            )

            if "current_average_trade_return" in metrics:
                backtest_metrics.current_average_trade_return = \
                    current_avg_return[0]
            if "current_average_trade_return_percentage" in metrics:
                backtest_metrics.current_average_trade_return_percentage =\
                    current_avg_return[1]
        except OperationalException as e:
            logger.warning(f"current_average_trade_return failed: {e}")

    if "current_average_trade_duration" in metrics:
        try:
            current_avg_duration = get_current_average_trade_duration(
                backtest_run.trades, backtest_run
            )
            backtest_metrics.current_average_trade_duration = \
                current_avg_duration
        except OperationalException as e:
            logger.warning(f"current_average_trade_duration failed: {e}")

    if ("current_average_trade_loss" in metrics
            or "current_average_trade_loss_percentage" in metrics):
        try:
            current_avg_loss = get_current_average_trade_loss(
                backtest_run.trades
            )
            if "current_average_trade_loss" in metrics:
                backtest_metrics.current_average_trade_loss = \
                    current_avg_loss[0]
            if "current_average_trade_loss_percentage" in metrics:
                backtest_metrics.current_average_trade_loss_percentage = \
                    current_avg_loss[1]
        except OperationalException as e:
            logger.warning(f"current_average_trade_loss failed: {e}")

    safe_set("number_of_positive_trades", get_positive_trades, backtest_run.trades, index=0)
    safe_set("percentage_positive_trades", get_positive_trades, backtest_run.trades, index=1)
    safe_set("number_of_negative_trades", get_negative_trades, backtest_run.trades, index=0)
    safe_set("percentage_negative_trades", get_negative_trades, backtest_run.trades, index=1)
    safe_set("median_trade_return", get_median_trade_return, backtest_run.trades, index=0)
    safe_set("median_trade_return_percentage", get_median_trade_return, backtest_run.trades, index=1)
    safe_set("number_of_trades", get_number_of_trades, backtest_run.trades)
    safe_set("number_of_trades_closed", get_number_of_closed_trades, backtest_run.trades)
    safe_set("number_of_trades_opened", get_number_of_open_trades, backtest_run.trades)
    directional_statistics = get_directional_trade_statistics(
        backtest_run.trades
    )
    for metric_name, value in directional_statistics.items():
        if metric_name in metrics:
            setattr(backtest_metrics, metric_name, value)
    mae_mfe_statistics = get_trade_mae_mfe_statistics(backtest_run.trades)
    for metric_name, value in mae_mfe_statistics.items():
        if metric_name in metrics:
            setattr(backtest_metrics, metric_name, value)
    safe_set("average_trade_duration", get_average_trade_duration, backtest_run.trades)
    safe_set("average_win_duration", get_average_win_duration, backtest_run.trades)
    safe_set("average_loss_duration", get_average_loss_duration, backtest_run.trades)
    safe_set("average_trade_size", get_average_trade_size, backtest_run.trades)
    safe_set("equity_curve", get_equity_curve, backtest_run.portfolio_snapshots)
    safe_set("final_value", get_final_value, backtest_run.portfolio_snapshots)
    safe_set("cagr", get_cagr, backtest_run.portfolio_snapshots)
    safe_set("sharpe_ratio", get_sharpe_ratio, backtest_run.portfolio_snapshots, risk_free_rate)
    safe_set("rolling_sharpe_ratio", get_rolling_sharpe_ratio, backtest_run.portfolio_snapshots, risk_free_rate)
    safe_set("sortino_ratio", get_sortino_ratio, backtest_run.portfolio_snapshots, risk_free_rate)
    safe_set("omega_ratio", get_omega_ratio, backtest_run.portfolio_snapshots)
    safe_set("profit_factor", get_profit_factor, backtest_run.trades)
    safe_set("calmar_ratio", get_calmar_ratio, backtest_run.portfolio_snapshots)
    safe_set("annual_volatility", get_annual_volatility, backtest_run.portfolio_snapshots)
    safe_set("monthly_returns", get_monthly_returns, backtest_run.portfolio_snapshots)
    safe_set("yearly_returns", get_yearly_returns, backtest_run.portfolio_snapshots)
    safe_set("drawdown_series", get_drawdown_series, backtest_run.portfolio_snapshots)
    safe_set("ulcer_index", get_ulcer_index, backtest_run.portfolio_snapshots)
    safe_set("max_drawdown", get_max_drawdown, backtest_run.portfolio_snapshots)
    safe_set("max_drawdown_absolute", get_max_drawdown_absolute, backtest_run.portfolio_snapshots)
    safe_set("max_daily_drawdown", get_max_daily_drawdown, backtest_run.portfolio_snapshots)
    safe_set("max_drawdown_duration", get_max_drawdown_duration, backtest_run.portfolio_snapshots)
    safe_set("twr_equity_curve", get_twr_equity_curve, backtest_run.portfolio_snapshots)
    safe_set("twr_drawdown_series", get_twr_drawdown_series, backtest_run.portfolio_snapshots)
    safe_set("twr_max_drawdown", get_twr_max_drawdown, backtest_run.portfolio_snapshots)
    safe_set("twr_max_drawdown_duration", get_twr_max_drawdown_duration, backtest_run.portfolio_snapshots)
    safe_set("trades_per_year", get_trades_per_year, backtest_run.trades, backtest_run.backtest_start_date, backtest_run.backtest_end_date)
    safe_set("trades_per_week", get_trades_per_week, backtest_run.trades, backtest_run.backtest_start_date, backtest_run.backtest_end_date)
    safe_set("trades_per_month", get_trades_per_month, backtest_run.trades, backtest_run.backtest_start_date, backtest_run.backtest_end_date)
    safe_set("trades_per_day", get_trades_per_day, backtest_run.trades, backtest_run.backtest_start_date, backtest_run.backtest_end_date)
    safe_set("exposure_ratio", get_exposure_ratio, backtest_run.trades, backtest_run.backtest_start_date, backtest_run.backtest_end_date)
    safe_set("cumulative_exposure", get_cumulative_exposure, backtest_run.trades, backtest_run.backtest_start_date, backtest_run.backtest_end_date)
    safe_set("best_trade", get_best_trade, backtest_run.trades)
    safe_set("worst_trade", get_worst_trade, backtest_run.trades)
    safe_set("win_rate", get_win_rate, backtest_run.trades)
    safe_set("current_win_rate", get_current_win_rate, backtest_run.trades)
    safe_set("win_loss_ratio", get_win_loss_ratio, backtest_run.trades)
    safe_set("current_win_loss_ratio", get_current_win_loss_ratio, backtest_run.trades)
    safe_set("percentage_winning_months", get_percentage_winning_months, backtest_run.portfolio_snapshots)
    safe_set("percentage_winning_years", get_percentage_winning_years, backtest_run.portfolio_snapshots)
    safe_set("average_monthly_return", get_average_monthly_return, backtest_run.portfolio_snapshots)
    safe_set("average_monthly_return_winning_months", get_average_monthly_return_winning_months, backtest_run.portfolio_snapshots)
    safe_set("average_monthly_return_losing_months", get_average_monthly_return_losing_months, backtest_run.portfolio_snapshots)
    safe_set("best_month", get_best_month, backtest_run.portfolio_snapshots)
    safe_set("best_year", get_best_year, backtest_run.portfolio_snapshots)
    safe_set("worst_month", get_worst_month, backtest_run.portfolio_snapshots)
    safe_set("worst_year", get_worst_year, backtest_run.portfolio_snapshots)
    safe_set("gross_loss", get_gross_loss, backtest_run.trades)
    safe_set("gross_profit", get_gross_profit, backtest_run.trades)
    safe_set("cumulative_return_series", get_cumulative_return_series, backtest_run.portfolio_snapshots)
    safe_set("cumulative_return", get_cumulative_return, backtest_run.portfolio_snapshots)
    safe_set("var_95", get_value_at_risk, backtest_run.portfolio_snapshots, 0.95)
    safe_set("cvar_95", get_conditional_value_at_risk, backtest_run.portfolio_snapshots, 0.95)
    safe_set("max_consecutive_wins", get_max_consecutive_wins, backtest_run.trades)
    safe_set("max_consecutive_losses", get_max_consecutive_losses, backtest_run.trades)
    return backtest_metrics
