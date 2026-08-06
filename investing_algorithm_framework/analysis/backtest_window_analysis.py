"""Analytics helpers for inspecting backtest date windows."""
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from investing_algorithm_framework.domain import BacktestDateRange

from .markdown import create_markdown_table


class _BacktestWindowChartGrid:
    def __init__(self, specs: List[Any]):
        self.specs = specs

    def display_in_jupyter(
        self,
        *,
        base: Optional[str] = None,
        width: Union[int, str] = "100%",
        height: Union[int, str] = 480,
    ) -> Any:
        from IPython.display import HTML

        width_css = f"{width}px" if isinstance(width, int) else width
        charts = []
        for spec in self.specs:
            chart = spec.display_in_jupyter(
                base=base,
                width="100%",
                height=height,
            )._repr_html_()
            charts.append(f'<div style="min-width:0">{chart}</div>')

        return HTML(
            '<div style="display:grid;gap:16px;'
            'grid-template-columns:repeat('
            'auto-fit,minmax(min(100%,480px),1fr));'
            f'width:{width_css}">{"".join(charts)}</div>'
        )


def _hurst_exponent(series: pd.Series, max_lag: int = 100) -> float:
    """
    Estimate the Hurst exponent of a price series using the
    variance-of-log-price-differences method. < 0.5 mean-reverting,
    ~ 0.5 random walk, > 0.5 trending.
    """
    s = series.dropna().to_numpy()
    if len(s) < 20:
        return float("nan")
    max_lag = min(max_lag, len(s) // 2)
    tau = []
    for lag in range(2, max_lag):
        diff = s[lag:] - s[:-lag]
        if diff.size == 0:
            continue
        std = np.std(diff)
        if std <= 0 or not np.isfinite(std):
            continue
        tau.append(std)
    if len(tau) < 4:
        return float("nan")
    log_lags = np.log(np.arange(2, 2 + len(tau)))
    slope, _ = np.polyfit(log_lags, np.log(tau), 1)
    return float(slope)


def _trend_slope(price: pd.Series) -> Tuple[float, float]:
    """Log-price linear-regression slope (per bar) and R^2."""
    s = price.dropna()
    if len(s) < 5:
        return float("nan"), float("nan")
    y = np.log(s.to_numpy())
    x = np.arange(len(y), dtype=float)
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    ss_res = float(np.sum((y - fitted) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return float(slope), float(r2)


def _regime_label(total_return: float, volatility: float, hurst: float) -> str:
    """Quick heuristic regime tag for a window."""
    if not np.isfinite(volatility):
        return "unknown"
    high_vol = volatility >= 80  # >80% annualised vol = high-vol crypto regime
    if total_return >= 25 and (not np.isnan(hurst)) and hurst > 0.5:
        return "high-vol bull" if high_vol else "bull"
    if total_return <= -25:
        return "high-vol bear" if high_vol else "bear"
    if high_vol:
        return "high-vol sideways"
    return "sideways"


def analyze_backtest_windows(
    data: Dict[str, Tuple[BacktestDateRange, pd.DataFrame]],
    price_column: str = "Close",
    periods_per_year: int = 365,
    sma_period: int = 200,
    show: bool = True,
) -> List[Dict[str, Union[str, float, int]]]:
    """
    Compute return / risk / regime statistics for a collection of backtest
    windows over a reference OHLCV series and (optionally) render the
    result as a markdown table in a Jupyter notebook.

    Per-window metrics include:

    - Return: cumulative, mean period return, annualised volatility
    - Risk-adjusted: Sharpe, Sortino, Calmar, max drawdown
    - Distribution: skewness, kurtosis
    - Trend: log-price slope + R^2, Hurst exponent
    - Regime: % of bars above the SMA, heuristic regime label
      (bull / bear / sideways / high-vol variants)

    Args:
        data: Mapping ``label -> (BacktestDateRange, ohlcv_dataframe)``.
            Each dataframe must be indexed by a ``DatetimeIndex`` and
            contain the column referenced by ``price_column``.
        price_column: Column for return / drawdown calculations.
        periods_per_year: Annualisation factor (365 for daily/intraday
            crypto, 252 for daily equities).
        sma_period: SMA lookback used for the "% above SMA" regime proxy.
        show: When ``True`` and IPython is available, render the summary
            table; the detailed list is always returned.
    """
    summary_data: List[Dict[str, str]] = []
    detailed_analysis: List[Dict[str, Union[str, float, int]]] = []

    for key, (date_range, df) in data.items():
        sliced = df[date_range.start_date:date_range.end_date].copy()
        if sliced.empty:
            continue

        price = sliced[price_column]
        returns = price.pct_change().dropna()
        if returns.empty:
            continue

        start_price = float(price.iloc[0])
        end_price = float(price.iloc[-1])
        total_return = (end_price / start_price - 1) * 100
        pct = returns * 100
        mean_return = float(pct.mean())
        volatility = float(pct.std() * np.sqrt(periods_per_year))

        sharpe = (
            (mean_return * periods_per_year) / volatility
            if volatility > 0 else 0.0
        )
        downside = pct[pct < 0]
        downside_vol = (
            float(downside.std() * np.sqrt(periods_per_year))
            if not downside.empty else 0.0
        )
        sortino = (
            (mean_return * periods_per_year) / downside_vol
            if downside_vol > 0 else 0.0
        )

        rolling_max = price.cummax()
        drawdown = (price / rolling_max - 1) * 100
        max_drawdown = float(drawdown.min())
        annual_return = (
            (1 + total_return / 100) ** (periods_per_year / max(len(price), 1))
            - 1
        ) * 100
        calmar = (
            annual_return / abs(max_drawdown)
            if max_drawdown < 0 else 0.0
        )

        skew = float(pct.skew()) if len(pct) > 2 else float("nan")
        kurt = float(pct.kurtosis()) if len(pct) > 3 else float("nan")

        slope, r2 = _trend_slope(price)
        hurst = _hurst_exponent(price)
        sma = price.rolling(window=sma_period, min_periods=1).mean()
        pct_above_sma = float((price > sma).mean() * 100)
        regime = _regime_label(total_return, volatility, hurst)

        abs_returns = pct.abs()
        high_vol = int((abs_returns > abs_returns.quantile(0.8)).sum())
        low_vol = int((abs_returns < abs_returns.quantile(0.2)).sum())
        up = int((pct > 0).sum())
        down = int((pct < 0).sum())
        total = int(len(returns))

        duration_days = (date_range.end_date - date_range.start_date).days
        start_str = date_range.start_date.strftime("%Y-%m-%d")
        end_str = date_range.end_date.strftime("%Y-%m-%d")

        summary_data.append({
            "window": key,
            "date_range": f"{start_str} to {end_str}",
            "days": str(duration_days),
            "regime": regime,
            "cum_return": f"{total_return:.2f}%",
            "vol_ann": f"{volatility:.2f}%",
            "sharpe": f"{sharpe:.2f}",
            "sortino": f"{sortino:.2f}",
            "calmar": f"{calmar:.2f}",
            "max_dd": f"{max_drawdown:.2f}%",
            "skew": f"{skew:.2f}",
            "kurtosis": f"{kurt:.2f}",
            "hurst": f"{hurst:.2f}",
            f"%>SMA{sma_period}": f"{pct_above_sma:.1f}%",
            "up%": f"{up / total * 100:.1f}%",
            "high_vol%": f"{high_vol / total * 100:.1f}%",
        })

        detailed_analysis.append({
            "name": key,
            "regime": regime,
            "total_return": total_return,
            "annual_return": annual_return,
            "volatility": volatility,
            "downside_volatility": downside_vol,
            "sharpe_ratio": sharpe,
            "sortino_ratio": sortino,
            "calmar_ratio": calmar,
            "max_drawdown": max_drawdown,
            "skew": skew,
            "kurtosis": kurt,
            "hurst_exponent": hurst,
            "trend_slope_log": slope,
            "trend_r2": r2,
            f"pct_above_sma_{sma_period}": pct_above_sma,
            "up_periods": up,
            "down_periods": down,
            "high_vol_periods": high_vol,
            "low_vol_periods": low_vol,
            "duration_days": duration_days,
            "total_periods": total,
            "mean_period_return": mean_return,
            "start_price": start_price,
            "end_price": end_price,
        })

    if show:
        table = create_markdown_table(summary_data)
        try:
            from IPython.display import Markdown, display
            display(Markdown(table))
        except ImportError:
            print(table)

    return detailed_analysis


def plot_backtest_windows(
    price_df: pd.DataFrame,
    rolling_windows: Iterable[Dict[str, BacktestDateRange]],
    price_column: str = "Close",
    title: str = "Backtest windows",
    train_color: str = "rgba(30, 120, 255, 0.35)",
    test_color: str = "rgba(255, 80, 20, 0.50)",
    gap_color: str = "rgba(240, 210, 0, 0.50)",
    theme: str = "finterion_dark",
    height: Union[int, str] = 520,
    width: Union[int, str] = "100%",
    initial_zoom: Optional[float] = None,
    variant: str = "all-in-one",
) -> Any:
    """
    Plot the reference price series with shaded bands for each rolling
    window's ``train_range`` / ``test_range`` (and the gap between them
    if present). ``all-in-one`` overlays every window in one chart;
    ``side-by-side`` returns a responsive grid with one chart per window.

    Call ``.display_in_jupyter()`` on the result to render in a notebook.
    """
    if variant not in {"all-in-one", "overlay", "side-by-side"}:
        raise ValueError(
            "variant must be 'all-in-one', 'overlay', or 'side-by-side'"
        )

    windows = list(rolling_windows)
    if variant == "side-by-side":
        index_tz = getattr(price_df.index, "tz", None)

        def _slice_boundary(value: Any) -> pd.Timestamp:
            boundary = pd.Timestamp(value)
            if index_tz is None and boundary.tzinfo is not None:
                return boundary.tz_localize(None)
            if index_tz is not None and boundary.tzinfo is None:
                return boundary.tz_localize(index_tz)
            if index_tz is not None:
                return boundary.tz_convert(index_tz)
            return boundary

        specs = []
        for index, window in enumerate(windows, start=1):
            if isinstance(window, dict):
                train = window.get("train_range")
                test = window.get("test_range")
                window_name = window.get("name")
            else:
                train = window.train_range
                test = window.test_range
                window_name = getattr(window, "name", None)

            if train is None:
                raise ValueError(f"Window {index} has no train_range")

            start = _slice_boundary(train.start_date)
            end_range = test if test is not None else train
            end = _slice_boundary(end_range.end_date)
            window_data = price_df.loc[
                (price_df.index >= start) & (price_df.index <= end)
            ]
            if window_data.empty:
                raise ValueError(f"No price data overlaps window {index}")

            label = window_name or f"Window {index}"
            specs.append(plot_backtest_windows(
                price_df=window_data,
                rolling_windows=[window],
                price_column=price_column,
                title=f"{title} - {label}" if title else label,
                train_color=train_color,
                test_color=test_color,
                gap_color=gap_color,
                theme=theme,
                height=height,
                width=width,
                initial_zoom=initial_zoom,
                variant="all-in-one",
            ))

        return _BacktestWindowChartGrid(specs)

    try:
        from finterion_charts import ChartSpec, Indicator, Price
        from finterion_charts.builder import SeriesType
    except ImportError as exc:
        raise ImportError(
            "plot_backtest_windows requires finterion-charts. "
            "Install with `pip install finterion-charts`."
        ) from exc

    price = price_df[price_column]

    # finterion-charts requires OHLCV bars; synthesise flat bars from the
    # close-only price series (open == high == low == close).
    # finterion-charts's _to_time_array assumes nanosecond datetime64 and
    # divides by 1_000_000 to get ms.  Exchange data typically uses
    # datetime64[us] (microseconds), so that division yields seconds instead of
    # milliseconds, pushing all timestamps to ~1970.
    #
    # Safest fix: convert to explicit int64 milliseconds and pass as a plain
    # numpy array.  numpy arrays have no .to_numpy() so _to_time_array skips
    # the datetime branch and treats the values as raw milliseconds directly.
    idx = price_df.index
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("UTC").tz_localize(None)
    time_ms = idx.astype("datetime64[ms]").astype("int64").to_numpy()
    price_vals = price.to_numpy()

    spec = ChartSpec(
        theme=theme,
        grid="horizontal",
        initial_zoom=initial_zoom,
    )
    spec.with_bars(
        time=time_ms,
        open=price_vals,
        high=price_vals,
        low=price_vals,
        close=price_vals,
    )

    # Price-space bounds used to span each band column full-height with a
    # 5 % pad so the fill doesn't clip at the axis edge.
    p_min = float(price.min())
    p_max = float(price.max())
    pad = (p_max - p_min) * 0.05
    band_top = p_max + pad
    band_bot = p_min - pad

    index_ts = price_df.index
    _index_tz = getattr(index_ts, "tz", None)

    def _norm(dt: Any) -> Any:
        """Normalise a date to be tz-compatible with the index."""
        if dt is None:
            return dt
        import datetime as _dt
        # If the index is tz-naive, strip tz from dt; if tz-aware, localise dt.
        if _index_tz is None:
            if hasattr(dt, "tzinfo") and dt.tzinfo is not None:
                return dt.replace(tzinfo=None)
        else:
            if hasattr(dt, "tzinfo") and dt.tzinfo is None:
                return dt.replace(tzinfo=_dt.timezone.utc)
        return dt

    overlays: list = []
    for i, window in enumerate(windows, start=1):
        # Support both BacktestWindow objects and legacy plain dicts.
        if isinstance(window, dict):
            train = window.get("train_range")
            test = window.get("test_range")
        else:
            train = window.train_range
            test = window.test_range

        for kind_label, date_range, color in (
            ("train", train, train_color),
            ("test", test, test_color),
        ):
            if date_range is None:
                continue
            col_u = f"_w{i}_{kind_label}_u"
            col_l = f"_w{i}_{kind_label}_l"
            start = _norm(date_range.start_date)
            end = _norm(date_range.end_date)
            mask = (index_ts >= start) & (index_ts <= end)
            spec.with_column(col_u, [band_top if m else None for m in mask])
            spec.with_column(col_l, [band_bot if m else None for m in mask])
            overlays.append(Indicator(
                values=col_u,
                lower_values=col_l,
                kind="band",
                color=color,
                label=f"W{i} {kind_label}",
            ))

        # Gap band between train end and test start.
        if (
            train is not None
            and test is not None
            and train.end_date < test.start_date
        ):
            col_u = f"_w{i}_gap_u"
            col_l = f"_w{i}_gap_l"
            train_end = _norm(train.end_date)
            test_start = _norm(test.start_date)
            mask = (index_ts > train_end) & (index_ts < test_start)
            spec.with_column(col_u, [band_top if m else None for m in mask])
            spec.with_column(col_l, [band_bot if m else None for m in mask])
            overlays.append(Indicator(
                values=col_u,
                lower_values=col_l,
                kind="band",
                color=gap_color,
                label=f"W{i} gap",
            ))

    spec.add_panel(Price(
        id="price",
        weight=1,
        title=title or price_column,
        type=SeriesType.line,
        overlays=overlays or None,
    ))

    return spec.validate()


def plot_window_correlation_matrix(
    assets_data: Dict[str, pd.DataFrame],
    date_range: Optional[BacktestDateRange] = None,
    price_column: str = "Close",
    title: Optional[str] = None,
    theme: str = "finterion_dark",
    color_scale: Tuple[str, str, str] = (
        "#2166ac",
        "#f7f7f7",
        "#b2182b",
    ),
) -> Any:
    """
    Pairwise return-correlation heatmap across multiple assets for a given
    window. ``assets_data`` is a mapping ``symbol -> ohlcv_dataframe``.
    If ``date_range`` is ``None`` the full overlapping range is used.
    Returns a ``finterion_charts.ChartSpec``.
    """
    try:
        from finterion_charts import ChartSpec, Heatmap
    except ImportError as exc:
        raise ImportError(
            "plot_window_correlation_matrix requires finterion-charts. "
            "Install with `pip install finterion-charts`."
        ) from exc

    returns = {}
    for symbol, df in assets_data.items():
        if date_range is not None:
            df = df[date_range.start_date:date_range.end_date]
        if df.empty or price_column not in df.columns:
            continue
        returns[symbol] = df[price_column].pct_change()

    if not returns:
        raise ValueError("No data available for the requested window.")

    ret_df = pd.DataFrame(returns).dropna(how="all")
    corr = ret_df.corr()

    if title is None:
        if date_range is not None:
            title = (
                f"Return correlations "
                f"{date_range.start_date:%Y-%m-%d} to "
                f"{date_range.end_date:%Y-%m-%d}"
            )
        else:
            title = "Return correlations"

    spec = ChartSpec(theme=theme).add_panel(Heatmap(
        id="window-correlations",
        title=title,
        weight=1,
        rows=list(corr.index),
        cols=list(corr.columns),
        values=corr.values.tolist(),
        format="fixed2",
        range=1,
        color_scale=color_scale,
        x_label="Asset",
        y_label="Asset",
    ))
    return spec.validate()
