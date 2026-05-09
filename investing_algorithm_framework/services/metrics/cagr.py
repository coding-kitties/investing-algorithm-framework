"""
The Compound Annual Growth Rate (CAGR) normalizes returns over a one-year
period, allowing you to compare performance across different timeframes.
It assumes the investment grows at a steady rate and compounds over time.

This formula is suitable whether your data spans:

* Less than a year (e.g. 30 days)
* Exactly a year (365 days)
* More than a year (e.g. 500 days)

When portfolio snapshots carry external ``cash_flow`` (deposits or
withdrawals absorbed via :meth:`Context.sync_portfolio`), CAGR is computed
using the **time-weighted return (TWR)** convention: per-period returns
subtract the period's cash flow before chaining, so external capital does
not inflate the reported growth rate.
"""

import pandas as pd
from typing import List
from investing_algorithm_framework.domain import PortfolioSnapshot


def get_cagr(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the time-weighted Compound Annual Growth Rate (CAGR) of a
    backtest report.

    The formula is the standard CAGR applied to a TWR-chained growth
    factor:

        period_return_t = (V_t - cash_flow_t) / V_{t-1} - 1
        growth = ∏ (1 + period_return_t)
        CAGR   = growth ^ (365 / num_days) - 1

    Where ``cash_flow_t`` is the net external deposit / withdrawal that
    landed between snapshot ``t-1`` and snapshot ``t``. With no cash
    flows the formula degenerates to the classic ``(end/start)^(1/yrs) - 1``.

    Args:
        snapshots (list[Snapshot]): A list of snapshots ordered by
            creation date.

    Returns:
        Float: The CAGR as a decimal. Returns 0.0 if not enough
            data is available.
    """

    if len(snapshots) < 2:
        return 0.0  # Not enough data

    data = [
        (s.total_value, s.created_at, getattr(s, "cash_flow", 0) or 0)
        for s in snapshots
    ]
    df = pd.DataFrame(data, columns=["total_value", "created_at", "cash_flow"])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').reset_index(drop=True)

    start_value = df.iloc[0]['total_value']
    start_date = df.iloc[0]['created_at']
    end_date = df.iloc[-1]['created_at']
    num_days = (end_date - start_date).days

    if num_days == 0 or start_value == 0:
        return 0.0

    growth = 1.0
    for i in range(1, len(df)):
        prev_v = df.iloc[i - 1]['total_value']
        curr_v = df.iloc[i]['total_value']
        cf = df.iloc[i]['cash_flow']
        if prev_v == 0:
            continue
        period_return = (curr_v - cf - prev_v) / prev_v
        growth *= (1.0 + period_return)

    if growth <= 0:
        return -1.0

    return growth ** (365 / num_days) - 1
