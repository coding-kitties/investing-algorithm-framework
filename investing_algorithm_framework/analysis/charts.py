"""Standalone Finterion charts for backtest analysis."""

from typing import Iterable

import numpy as np
import pandas as pd
from finterion_charts import ChartSpec, Indicator

from investing_algorithm_framework.domain import Backtest, BacktestDateRange
from investing_algorithm_framework.domain.backtesting.backtest_utils import \
    BacktestIndex
from investing_algorithm_framework.services.metrics.equity_curve import \
    get_equity_curve


_EQUITY_COLORS = (
    "#10b981", "#3b82f6", "#f59e0b", "#ef4444",
    "#8b5cf6", "#06b6d4", "#ec4899", "#84cc16",
)


def _prepare_equity_curve(
    equity: Iterable[tuple[object, object]],
    daterange: BacktestDateRange,
    label: str,
    *,
    normalize: bool,
    include_prior: bool = False,
) -> pd.Series:
    frame = pd.DataFrame(equity, columns=["value", "datetime"])
    frame["datetime"] = pd.to_datetime(frame["datetime"], utc=True)
    if frame["datetime"].isna().any():
        raise ValueError(f"{label}: invalid equity timestamp.")
    frame = frame.sort_values("datetime")
    prior = frame.loc[
        frame["datetime"] < daterange.start_date
    ] if include_prior else None
    frame = frame.loc[frame["datetime"].between(
        daterange.start_date, daterange.end_date,
    )]
    if prior is not None and not prior.empty:
        prior = prior.loc[prior["datetime"] == prior["datetime"].iloc[-1]]
        frame = pd.concat([prior, frame])
    if frame.empty:
        raise ValueError(f"{label}: no equity observations in daterange.")
    values = pd.to_numeric(
        frame["value"], errors="raise",
    ).to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError(f"{label}: equity must be finite.")
    frame["value"] = values
    frame = frame.drop_duplicates(subset=["datetime", "value"])
    values = frame["value"].to_numpy(dtype=float)
    if normalize and values[0] <= 0:
        raise ValueError(
            f"{label}: initial selected equity must be "
            "positive for normalization."
        )
    times = pd.DatetimeIndex(frame["datetime"]).to_numpy(
        dtype="datetime64[ms]",
    ).astype("int64")
    if len(np.unique(times)) != len(times):
        raise ValueError(
            f"{label}: duplicate equity timestamps at millisecond resolution."
        )
    if normalize:
        values = values / values[0]
        if not np.isfinite(values).all():
            raise ValueError(f"{label}: normalized equity must be finite.")
    return pd.Series(values, index=times)


def create_layered_equity_chart(
    backtests: Backtest | BacktestIndex | Iterable[Backtest],
    daterange: BacktestDateRange,
    *,
    normalize: bool = True,
    benchmark: pd.Series | None = None,
    benchmark_label: str = "Benchmark",
) -> ChartSpec:
    """Overlay equity curves for runs overlapping a date range.

    Args:
        backtests: A Backtest, an iterable of Backtests, or a BacktestIndex.
            An index loads each referenced bundle once, one at a time.
            All studies and both engines in those bundles are considered.
        daterange: Inclusive UTC range used to select equity observations.
        normalize: Normalize each curve to 1 at its first selected observation.
            False keeps absolute portfolio values in each run's quote currency.
            Both modes use a linear axis, not a logarithmic scale.
        benchmark: Optional values indexed by DatetimeIndex, available only
            with normalize=True. The last available quote is sampled at each
            chart timestamp, including a supplied quote before daterange.
            The first available sampled value is normalized to 1. Quotes are
            carried forward through market closures, never filled backward
            from the future. No benchmark data is downloaded by this helper.
        benchmark_label: Legend label for the benchmark overlay.

    Returns:
        A validated Finterion ChartSpec with one panel and a labeled line
        per overlapping run. Normalized curves start at 1; absolute curves
        retain their original values. Missing observations remain gaps,
        without interpolation or extending a run beyond its recorded history.
        Identical repeated observations, including duplicate opening
        snapshots from the vector engine, are collapsed.
        The shared vertical range includes all selected curves.

        Use display_in_jupyter() in notebooks or show() in Python scripts.
        No chart is displayed or file written by this function.

    Raises:
        TypeError: If inputs are not supported backtest/date-range objects,
            normalize is not a bool, or benchmark has an unsupported
            type/index.
        ValueError: If no runs overlap, selected equity is missing/invalid,
            timestamps conflict or collide at millisecond resolution, or an
            initial selected equity value is not positive when normalizing,
            the padded equity range cannot be represented as finite bounds,
            or a benchmark is invalid/unavailable or used in absolute mode.

    Stored equity metrics are preferred; portfolio snapshots are used when
    equity metrics are absent. Normalization compares portfolio value, not
    cash-flow-adjusted returns. Inputs and persisted metrics are not mutated.
    Compare runs with the same quote currency when using absolute values.
    """
    if not isinstance(normalize, bool):
        raise TypeError("normalize must be a bool.")
    if not isinstance(daterange, BacktestDateRange):
        raise TypeError("daterange must be a BacktestDateRange.")
    if benchmark is not None:
        if not normalize:
            raise ValueError("Benchmark overlays require normalize=True.")
        if not isinstance(benchmark, pd.Series):
            raise TypeError("benchmark must be a pandas Series.")
        if not isinstance(benchmark.index, pd.DatetimeIndex):
            raise TypeError("benchmark must have a DatetimeIndex.")
        if not isinstance(benchmark_label, str) or not benchmark_label.strip():
            raise ValueError("benchmark_label must be a nonempty string.")
    if isinstance(backtests, BacktestIndex):
        sources = backtests.iter_backtests()
    elif isinstance(backtests, Backtest):
        sources = iter((backtests,))
    else:
        sources = iter(backtests)

    curves: dict[str, pd.Series] = {}
    labels: list[str] = []
    for backtest in sources:
        if not isinstance(backtest, Backtest):
            raise TypeError("backtests must contain Backtest objects.")
        for study in backtest.list_studies():
            for engine in ("vector", "event"):
                for run_index, run in enumerate(
                    backtest.get_runs(engine, study=study),
                ):
                    if run.backtest_end_date < daterange.start_date \
                            or run.backtest_start_date > daterange.end_date:
                        continue
                    window = run.backtest_window.name \
                        or run.backtest_date_range_name \
                        or f"run {run_index + 1}"
                    label = (
                        f"{backtest.algorithm_id} / {study} / "
                        f"{engine} / {window}"
                    )
                    metrics = run.backtest_metrics
                    if metrics is not None and metrics.equity_curve:
                        equity = list(metrics.equity_curve)
                    else:
                        equity = get_equity_curve(list(
                            run.portfolio_snapshots,
                        ))
                    name = f"equity_{len(curves)}"
                    curves[name] = _prepare_equity_curve(
                        equity, daterange, label, normalize=normalize,
                    )
                    labels.append(label)

    if not curves:
        raise ValueError("No backtest runs overlap daterange.")

    aligned = pd.concat(curves, axis=1).sort_index()
    if benchmark is not None:
        prices = _prepare_equity_curve(
            [(value, timestamp) for timestamp, value in benchmark.items()],
            daterange, benchmark_label, normalize=False, include_prior=True,
        )
        sampled = prices.reindex(aligned.index, method="ffill")
        available = sampled.dropna()
        if available.empty:
            raise ValueError(
                f"{benchmark_label}: no quotes available at chart timestamps."
            )
        if available.iloc[0] <= 0:
            raise ValueError(
                f"{benchmark_label}: initial sampled value must be positive."
            )
        sampled = sampled / available.iloc[0]
        if not np.isfinite(sampled.dropna().to_numpy()).all():
            raise ValueError(
                f"{benchmark_label}: normalized benchmark must be finite."
            )
        aligned["benchmark"] = sampled
        curves["benchmark"] = sampled
        labels.append(benchmark_label)
    # Finterion otherwise scales this panel from only its primary line.
    minimum = float(aligned.min().min())
    maximum = float(aligned.max().max())
    padding = 0.02 if normalize else max(abs(minimum), abs(maximum), 1) * 0.02
    y_range = (
        minimum - padding, maximum + padding,
    )
    if not np.isfinite(y_range).all():
        raise ValueError("Equity range is too large to render with padding.")
    spec = ChartSpec(
        theme="finterion-light", grid="horizontal", show_legend=True,
    )
    # Finterion requires OHLC anchors for a shared time axis; no price
    # panel is rendered, so these anchors are not plotted as equity.
    anchors = np.ones(len(aligned))
    spec.with_bars(
        time=aligned.index.to_numpy(), open=anchors, high=anchors,
        low=anchors, close=anchors,
    )
    overlays = []
    for index, name in enumerate(curves):
        spec.with_column(name, aligned[name].to_numpy())
        if index:
            overlays.append(Indicator(
                values=name, kind="line", label=labels[index], id=name,
                color=(
                    "#64748b" if name == "benchmark"
                    else _EQUITY_COLORS[index % len(_EQUITY_COLORS)]
                ),
            ))
    spec.add_panel(Indicator.panel(
        id="equity", weight=1, values="equity_0", kind="line",
        color=_EQUITY_COLORS[0], label=labels[0],
        title=(
            "Normalized Equity (start = 1)" if normalize else "Absolute Equity"
        ),
        ref_lines=[1] if normalize else None,
        overlays=overlays, y_range=y_range,
    ))
    return spec.validate()
