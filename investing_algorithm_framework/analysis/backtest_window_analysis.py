"""Analytics helpers for inspecting backtest date windows."""
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from investing_algorithm_framework.domain import BacktestDateRange

from .markdown import create_markdown_table


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
    train_color: str = "rgba(46, 134, 222, 0.18)",
    test_color: str = "rgba(46, 204, 113, 0.25)",
    gap_color: str = "rgba(241, 196, 15, 0.18)",
) -> Any:
    """
    Plot the reference price series with shaded bands for each rolling
    window's ``train_range`` / ``test_range`` (and the gap between them
    if present). Returns a Plotly ``Figure``.
    """
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise ImportError(
            "plot_backtest_windows requires plotly. "
            "Install with `pip install plotly`."
        ) from exc

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=price_df.index,
        y=price_df[price_column],
        mode="lines",
        name=price_column,
        line=dict(color="#222", width=1.2),
    ))

    shapes = []
    annotations = []
    for i, window in enumerate(rolling_windows, start=1):
        train = window.get("train_range")
        test = window.get("test_range")
        if train is not None:
            shapes.append(dict(
                type="rect", xref="x", yref="paper",
                x0=train.start_date, x1=train.end_date,
                y0=0, y1=1,
                fillcolor=train_color, line=dict(width=0), layer="below",
            ))
            annotations.append(dict(
                x=train.start_date, y=1.02, xref="x", yref="paper",
                text=f"W{i} train", showarrow=False,
                font=dict(size=10, color="#2e86de"),
            ))
        if train is not None and test is not None \
                and train.end_date < test.start_date:
            shapes.append(dict(
                type="rect", xref="x", yref="paper",
                x0=train.end_date, x1=test.start_date,
                y0=0, y1=1,
                fillcolor=gap_color, line=dict(width=0), layer="below",
            ))
        if test is not None:
            shapes.append(dict(
                type="rect", xref="x", yref="paper",
                x0=test.start_date, x1=test.end_date,
                y0=0, y1=1,
                fillcolor=test_color, line=dict(width=0), layer="below",
            ))
            annotations.append(dict(
                x=test.start_date, y=1.06, xref="x", yref="paper",
                text=f"W{i} test", showarrow=False,
                font=dict(size=10, color="#1e8449"),
            ))

    fig.update_layout(
        title=title,
        shapes=shapes,
        annotations=annotations,
        xaxis_title="Date",
        yaxis_title=price_column,
        template="plotly_white",
        height=520,
        margin=dict(l=40, r=20, t=80, b=40),
    )
    return fig


def plot_window_correlation_matrix(
    assets_data: Dict[str, pd.DataFrame],
    date_range: Optional[BacktestDateRange] = None,
    price_column: str = "Close",
    title: Optional[str] = None,
) -> Any:
    """
    Pairwise return-correlation heatmap across multiple assets for a given
    window. ``assets_data`` is a mapping ``symbol -> ohlcv_dataframe``.
    If ``date_range`` is ``None`` the full overlapping range is used.
    Returns a Plotly ``Figure``.
    """
    try:
        import plotly.graph_objects as go
    except ImportError as exc:
        raise ImportError(
            "plot_window_correlation_matrix requires plotly."
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

    fig = go.Figure(data=go.Heatmap(
        z=corr.values,
        x=list(corr.columns),
        y=list(corr.index),
        zmin=-1, zmax=1,
        colorscale="RdBu",
        reversescale=True,
        text=np.round(corr.values, 2),
        texttemplate="%{text}",
        hovertemplate="%{y} vs %{x}: %{z:.2f}<extra></extra>",
    ))
    if title is None:
        if date_range is not None:
            title = (
                f"Return correlations "
                f"{date_range.start_date:%Y-%m-%d} to "
                f"{date_range.end_date:%Y-%m-%d}"
            )
        else:
            title = "Return correlations"
    fig.update_layout(
        title=title,
        template="plotly_white",
        height=520,
        margin=dict(l=80, r=40, t=80, b=80),
    )
    return fig
