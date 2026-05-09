"""Helpers for converting portfolio snapshots into time-weighted return
(TWR) series.

The simple ``total_value.pct_change()`` is wrong as soon as a portfolio
absorbs external deposits or withdrawals via
:meth:`Context.sync_portfolio` — a $100 deposit looks like $100 of
trading P&L. These helpers subtract ``snapshot.cash_flow`` from the
period's ending value before computing the return, so external capital
no longer inflates the metric.

Snapshots without a ``cash_flow`` attribute (or with it set to ``None``
or ``0``) degrade gracefully to the classic ``pct_change`` behaviour.
"""
from __future__ import annotations

from typing import Iterable

import pandas as pd


def snapshots_to_dataframe(snapshots: Iterable) -> pd.DataFrame:
    """Build a 3-column dataframe ``(created_at, total_value, cash_flow)``
    indexed by ``created_at``."""
    data = [
        (s.created_at, s.total_value, getattr(s, "cash_flow", 0) or 0)
        for s in snapshots
    ]
    df = pd.DataFrame(
        data, columns=["created_at", "total_value", "cash_flow"]
    )
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').drop_duplicates('created_at')\
        .set_index('created_at')
    return df


def daily_twr_returns(snapshots: Iterable, ffill: bool = True) -> pd.Series:
    """Return a daily TWR series indexed by date.

    For each day ``d``:

        r_d = (V_d - cash_flow_d) / V_{d-1} - 1

    Where ``V_d`` is end-of-day total value and ``cash_flow_d`` is the
    sum of external cash flows that landed during day ``d``. Days with a
    zero ``V_{d-1}`` are dropped.

    Args:
        snapshots: Iterable of portfolio snapshots.
        ffill: When ``True`` (default), forward-fill end-of-day values
            across calendar gaps (weekends, holidays). This matches the
            historical ``pct_change`` behaviour used by the std/sharpe
            metrics where days without a new snapshot register a 0%
            return. Set to ``False`` to drop gap days entirely (used by
            the volatility metric).
    """
    df = snapshots_to_dataframe(snapshots)
    if df.empty:
        return pd.Series(dtype=float)

    daily_value = df['total_value'].resample('1D').last()
    if ffill:
        daily_value = daily_value.ffill()
    else:
        daily_value = daily_value.dropna()
    daily_cf = df['cash_flow'].resample('1D').sum()
    daily_cf = daily_cf.reindex(daily_value.index, fill_value=0)
    prev_value = daily_value.shift(1)
    returns = (daily_value - daily_cf) / prev_value - 1
    return returns.dropna()
