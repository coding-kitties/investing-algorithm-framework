"""
The Ulcer Index (UI) is a downside-risk measure that captures both the
**depth** and **duration** of drawdowns, unlike standard deviation
(which penalizes upside volatility equally) or max drawdown (which
only captures the single worst peak-to-trough decline and ignores how
long the portfolio spent underwater).

| **Ulcer Index** | **Interpretation**                                    |
| ---------------- | ------------------------------------------------------ |
| **0.00 – 0.02**  | Very low downside risk — shallow, short drawdowns       |
| **0.02 – 0.05**  | Moderate — typical for balanced strategies              |
| **0.05 – 0.10**  | Elevated — deep and/or prolonged drawdowns              |
| **> 0.10**       | High — significant time spent in deep drawdown          |

Ulcer Index Formula (over ``n`` drawdown observations ``D_i``,
expressed as the same signed fraction used by
:func:`~investing_algorithm_framework.services.metrics.get_drawdown_series`,
e.g. ``-0.125`` for a 12.5% drawdown):

    UI = sqrt( (1/n) * sum(D_i^2) )

Because it squares every drawdown observation (not just the single
worst one), a long, shallow drawdown and a short, deep drawdown of
equal "area" can register a similar Ulcer Index — making it a useful
complement to :func:`~.drawdown.get_max_drawdown` for judging how
uncomfortable a strategy is to actually hold.
"""
import math
from typing import List

from investing_algorithm_framework.domain import PortfolioSnapshot

from .drawdown import get_drawdown_series


def get_ulcer_index(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the Ulcer Index from a backtest's drawdown series.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots.

    Returns:
        float: The Ulcer Index, expressed in the same fractional unit
            as ``get_drawdown_series`` (e.g. ``0.05`` for a "5%"-scale
            downside profile). Returns ``0.0`` when there is not enough
            data.
    """
    drawdown_series = get_drawdown_series(snapshots)

    if not drawdown_series:
        return 0.0

    squared_drawdowns = [drawdown ** 2 for drawdown, _ in drawdown_series]
    return float(math.sqrt(sum(squared_drawdowns) / len(squared_drawdowns)))
