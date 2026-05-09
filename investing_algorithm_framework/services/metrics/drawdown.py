""""
Max Drawdown (MDD) — a key risk metric that shows the worst
peak-to-trough decline of a portfolio:

| **Max Drawdown (%)** | **Interpretation**                                                   |
|-----------------------|----------------------------------------------------------------------|
| **0% to -5%**         | 🟢 Excellent — Very low risk, typical for conservative strategies     |
| **-5% to -10%**       | ✅ Good — Moderate volatility, acceptable for balanced portfolios     |
| **-10% to -20%**      | ⚠️ Elevated Risk — Common in growth or actively managed strategies    |
| **-20% to -40%**      | 🔻 High Risk — Significant drawdown, typical of aggressive strategies |
| **> -40%**            | 🚨 Very High Risk — Risk of capital loss or strategy failure          |
"""
from typing import List, Tuple
import pandas as pd
from datetime import datetime
from investing_algorithm_framework.domain import PortfolioSnapshot, Trade
from .equity_curve import get_equity_curve, get_twr_equity_curve


def get_drawdown_series(snapshots: List[PortfolioSnapshot]) -> List[Tuple[float, datetime]]:
    """
    Calculate the drawdown series of a backtest report.

    The drawdown is calculated as the percentage difference
    between the current equity value and the maximum equity value
    observed up to that point in time.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots

    Returns:
        List[Tuple[datetime, float]]: A list of tuples with datetime
            and drawdown percentage. The drawdown is expressed as a
            negative percentage, where 0% means no drawdown and -100%
            means the portfolio has lost all its value.
    """
    equity_curve = get_equity_curve(snapshots)

    drawdown_series = []
    max_value = None

    for value, timestamp in equity_curve:
        # Skip zero or negative values to avoid division by zero
        if value <= 0:
            drawdown_series.append((0.0, timestamp))
            continue

        if max_value is None or max_value <= 0:
            max_value = value
        max_value = max(max_value, value)
        drawdown = (value - max_value) / max_value  # This will be <= 0
        drawdown_series.append((drawdown, timestamp))

    return drawdown_series


def get_max_drawdown(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the maximum drawdown of the portfolio as a percentage from the peak.

    Max Drawdown is the maximum observed loss from a peak to a
    trough before a new peak is achieved.

    It is expressed here as a negative percentage.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots

    Returns:
        float: The maximum drawdown as a negative percentage (e.g., -12.5 for a 12.5% drawdown).
    """
    equity_curve = get_equity_curve(snapshots)

    if not equity_curve:
        return 0.0

    peak = equity_curve[0][0]

    # Handle zero or negative starting value
    if peak <= 0:
        # Find first positive value as the peak
        for equity, _ in equity_curve:
            if equity > 0:
                peak = equity
                break
        else:
            # No positive values found
            return 0.0

    max_drawdown_pct = 0.0

    for equity, _ in equity_curve:
        # Skip non-positive values
        if equity <= 0:
            continue

        if equity > peak:
            peak = equity

        # Avoid division by zero (shouldn't happen now but extra safety)
        if peak <= 0:
            continue

        drawdown_pct = (equity - peak) / peak  # Will be 0 or negative
        max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)

    return abs(max_drawdown_pct)


def get_max_daily_drawdown(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the worst single-day decline of the portfolio as a percentage.

    This is the largest day-over-day percentage drop in equity,
    NOT the peak-to-trough drawdown (use get_max_drawdown for that).

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots

    Returns:
        float: The maximum single-day drawdown as a positive percentage
            (e.g., 0.05 for a 5% single-day decline).
    """
    # Create DataFrame from snapshots
    data = [(s.created_at, s.total_value) for s in snapshots]
    df = pd.DataFrame(data, columns=["created_at", "total_value"])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').drop_duplicates('created_at')\
        .set_index('created_at')

    # Resample to daily frequency using last value of the day
    daily_df = df.resample('1D').last().dropna()

    if daily_df.empty:
        return 0.0

    # Filter out non-positive values
    positive_values = daily_df[daily_df['total_value'] > 0]['total_value']

    if positive_values.empty or len(positive_values) < 2:
        return 0.0

    # Compute day-over-day returns; the worst single-day decline
    # is the most negative return (ignore positive returns)
    daily_returns = positive_values.pct_change().dropna()
    negative_returns = daily_returns[daily_returns < 0]

    if negative_returns.empty:
        return 0.0

    return abs(negative_returns.min())

def get_max_drawdown_duration(snapshots: List[PortfolioSnapshot]) -> int:
    """
    Calculate the maximum duration of drawdown in days.

    This is the longest period (in calendar days) where the portfolio
    equity was below its peak.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots

    Returns:
        int: The maximum drawdown duration in calendar days.
    """
    equity_curve = get_equity_curve(snapshots)
    if not equity_curve:
        return 0

    peak = equity_curve[0][0]
    max_duration = 0
    drawdown_start = None

    for equity, timestamp in equity_curve:
        if equity < peak:
            # Entering or continuing a drawdown
            if drawdown_start is None:
                drawdown_start = timestamp
        else:
            # Recovered to or above the peak
            if drawdown_start is not None:
                elapsed = (timestamp - drawdown_start).days
                max_duration = max(max_duration, elapsed)
                drawdown_start = None
            peak = equity

    # If still in drawdown at the end of the series
    if drawdown_start is not None and len(equity_curve) > 0:
        last_timestamp = equity_curve[-1][1]
        elapsed = (last_timestamp - drawdown_start).days
        max_duration = max(max_duration, elapsed)

    return max_duration


def get_max_drawdown_absolute(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the maximum absolute drawdown of the portfolio.

    This is the largest drop in equity (in currency units) from a peak to a trough
    during the backtest period.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots

    Returns:
        float: The maximum absolute drawdown as a positive number (e.g., €10,000).
    """
    equity_curve = get_equity_curve(snapshots)
    if not equity_curve:
        return 0.0

    peak = equity_curve[0][0]
    max_drawdown = 0.0

    for equity, _ in equity_curve:
        if equity > peak:
            peak = equity

        drawdown = peak - equity  # Drop from peak
        max_drawdown = max(max_drawdown, drawdown)

    return abs(max_drawdown)  # Return as positive number (e.g., €10,000)


# ---------------------------------------------------------------------------
# TWR (alpha-only) drawdown variants
# ---------------------------------------------------------------------------
#
# The drawdown functions above operate on raw ``total_value`` — i.e. the
# absolute account-value path including external deposits/withdrawals.
# That's the curve users typically want to see ("how deep did my account
# go in dollars?").
#
# These variants below operate on the TWR-growth curve so that a
# strategy that receives a $1,000 deposit during a drawdown does NOT
# have its drawdown artificially shortened/erased by the deposit. Use
# these when comparing risk profiles across portfolios that are funded
# differently.


def get_twr_drawdown_series(
    snapshots: List[PortfolioSnapshot],
) -> List[Tuple[float, datetime]]:
    """Drawdown series computed against the TWR-growth curve.

    Identical shape to :func:`get_drawdown_series` (negative percentages
    where 0% means "at high-water mark"), but external cash flows do
    not contaminate the high-water mark.
    """
    equity_curve = get_twr_equity_curve(snapshots)

    drawdown_series: List[Tuple[float, datetime]] = []
    max_value = None

    for value, timestamp in equity_curve:
        if value <= 0:
            drawdown_series.append((0.0, timestamp))
            continue
        if max_value is None or max_value <= 0:
            max_value = value
        max_value = max(max_value, value)
        drawdown = (value - max_value) / max_value
        drawdown_series.append((drawdown, timestamp))

    return drawdown_series


def get_twr_max_drawdown(snapshots: List[PortfolioSnapshot]) -> float:
    """Maximum drawdown of the TWR-growth curve, returned as a positive
    fraction (e.g. ``0.18`` for an 18% peak-to-trough decline in alpha).
    """
    equity_curve = get_twr_equity_curve(snapshots)
    if not equity_curve:
        return 0.0

    peak = equity_curve[0][0]
    if peak <= 0:
        for equity, _ in equity_curve:
            if equity > 0:
                peak = equity
                break
        else:
            return 0.0

    max_drawdown_pct = 0.0
    for equity, _ in equity_curve:
        if equity <= 0:
            continue
        if equity > peak:
            peak = equity
        if peak <= 0:
            continue
        drawdown_pct = (equity - peak) / peak
        max_drawdown_pct = min(max_drawdown_pct, drawdown_pct)

    return abs(max_drawdown_pct)


def get_twr_max_drawdown_duration(
    snapshots: List[PortfolioSnapshot],
) -> int:
    """Longest stretch in calendar days where the TWR-growth curve was
    below its high-water mark."""
    equity_curve = get_twr_equity_curve(snapshots)
    if not equity_curve:
        return 0

    peak = equity_curve[0][0]
    max_duration = 0
    drawdown_start = None

    for equity, timestamp in equity_curve:
        if equity < peak:
            if drawdown_start is None:
                drawdown_start = timestamp
        else:
            if drawdown_start is not None:
                elapsed = (timestamp - drawdown_start).days
                max_duration = max(max_duration, elapsed)
                drawdown_start = None
            peak = equity

    if drawdown_start is not None and len(equity_curve) > 0:
        last_timestamp = equity_curve[-1][1]
        elapsed = (last_timestamp - drawdown_start).days
        max_duration = max(max_duration, elapsed)

    return max_duration

