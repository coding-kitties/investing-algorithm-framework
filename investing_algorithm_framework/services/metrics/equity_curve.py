from datetime import datetime
from typing import List
from investing_algorithm_framework.domain import PortfolioSnapshot


def get_equity_curve(
    snapshots: List[PortfolioSnapshot]
) -> list[tuple[float, datetime]]:
    """
    Calculate the total size of the portfolio at each snapshot timestamp.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.
    Returns:
        list[tuple[datetime, float]]: A list of tuples with
            timestamps and total sizes.
    """
    series = []
    for snapshot in snapshots:
        timestamp = snapshot.created_at
        total_size = snapshot.total_value
        series.append((total_size, timestamp))

    # Sort by timestamp to ensure chronological order
    series.sort(key=lambda x: x[1])

    return series


def get_twr_equity_curve(
    snapshots: List[PortfolioSnapshot], base: float = 1.0
) -> list[tuple[float, datetime]]:
    """Equity curve scrubbed of external cash flows (TWR-growth series).

    Each step compounds the period's TWR return:

        r_t = (V_t - cash_flow_t) / V_{t-1} - 1
        equity_t = equity_{t-1} * (1 + r_t)

    Starting from ``base`` (default 1.0 → curve is "growth of $1"). This
    is the curve to use when comparing alpha across portfolios that
    receive different external capital — depositing $1,000 doesn't make
    the line jump, only trading P&L does.

    Snapshots without a ``cash_flow`` field fall back to the simple
    ``V_t / V_{t-1}`` ratio.

    Args:
        snapshots: Time-sorted (or unsorted; we sort) snapshots.
        base: Starting value of the curve. ``1.0`` for growth-of-$1,
            ``snapshots[0].total_value`` to anchor the first point on
            the raw account value.

    Returns:
        ``[(equity, timestamp), ...]`` matching the shape of
        :func:`get_equity_curve`.
    """
    sorted_snaps = sorted(snapshots, key=lambda s: s.created_at)
    if not sorted_snaps:
        return []

    series: list[tuple[float, datetime]] = []
    equity = float(base)
    series.append((equity, sorted_snaps[0].created_at))
    prev_value = float(sorted_snaps[0].total_value)

    for snap in sorted_snaps[1:]:
        curr_value = float(snap.total_value)
        cash_flow = float(getattr(snap, "cash_flow", 0) or 0)
        if prev_value > 0:
            ret = (curr_value - cash_flow) / prev_value - 1
            equity *= 1 + ret
        # else: prev_value is zero/negative → skip update, equity stays put
        series.append((equity, snap.created_at))
        prev_value = curr_value

    return series
