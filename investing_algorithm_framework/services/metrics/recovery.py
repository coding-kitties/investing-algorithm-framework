"""
🔍 What is Recovery Factor:
Recovery Factor =
🔹 Total Net Profit (how much you made overall)
➗
🔹 Max Drawdown (worst capital drop at any point)

This metric answers:

💡 "How much return did I get per unit of worst-case risk?"

🎯 Why this matters:
Even if a strategy has many small drawdowns, only the worst one is used.

A strategy that earns €100k total, but once dropped €50k from peak, has a
recovery factor of 2.0 — suggesting that it made 2x the worst pain it endured.

✅ Pros:
Simple and interpretable.

Useful when comparing strategies with very different drawdown profiles.

⚠️ Limitations:
It ignores the frequency or duration of drawdowns.

It can be misleading if net profit is inflated due to one lucky trend or
max drawdown happened early and was never tested again.

| **Recovery Factor** | **Interpretation**                                   | **Comments**                                                     |
| ------------------- | ---------------------------------------------------- | ---------------------------------------------------------------- |
| **< 1.0**           | ❌ *Poor* – Risk outweighs reward                     | Losing more in drawdowns than you're making overall              |
| **1.0 – 1.5**       | ⚠️ *Weak* – Barely recovering from drawdowns         | Net profit is only slightly higher than worst drawdown           |
| **1.5 – 2.0**       | 🤔 *Moderate* – Acceptable, but not robust           | Strategy is viable but may lack strong risk-adjusted performance |
| **2.0 – 3.0**       | ✅ *Good* – Solid recovery from worst drawdowns       | Indicates decent resilience and profitability                    |
| **3.0 – 5.0**       | 🚀 *Very Good* – Strong risk-adjusted performance    | Shows good ability to recover and generate consistent profit     |
| **> 5.0**           | 🏆 *Excellent* – Exceptional recovery vs. risk taken | Often seen in highly optimized or low-volatility strategies      |
| **∞ (Infinity)**    | 💡 *No drawdown* – Unrealistic or incomplete data    | Can happen if drawdown is zero — investigate carefully           |
"""
from typing import List

from investing_algorithm_framework.domain import PortfolioSnapshot
from .drawdown import get_max_drawdown_absolute
from .returns import get_total_return


def get_recovery_factor(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the recovery factor of a backtest report.

    The recovery factor is defined as:
        Recovery Factor = Total Net Profit / Maximum Drawdown

    This metric indicates how efficiently a trading strategy recovers
    from drawdowns. A higher recovery factor implies better
    risk-adjusted performance.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots
            from the backtest report.

    Returns:
        float: The recovery factor. Returns 0.0 if max drawdown is
            zero or undefined.
    """

    if not snapshots:
        return 0.0

    max_drawdown_absolute = get_max_drawdown_absolute(snapshots)
    net_profit, _ = get_total_return(snapshots)

    if max_drawdown_absolute == 0:
        return float('inf') if net_profit > 0 else 0.0

    return net_profit / max_drawdown_absolute


def get_recovery_time(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the recovery time of a backtest report.

    The recovery time is defined as the number of days it takes to recover
    from the maximum drawdown.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots
            from the backtest report.

    Returns:
        float: The recovery time in days. Returns 0.0 if no drawdown
            occurred.
    """

    if not snapshots:
        return 0.0

    max_drawdown_absolute = get_max_drawdown_absolute(snapshots)

    if max_drawdown_absolute == 0:
        return 0.0

    # Find the first snapshot after the maximum drawdown
    first_snapshot_after_drawdown = next(
        (s for s in snapshots if s.net_size >= max_drawdown_absolute), None)

    if not first_snapshot_after_drawdown:
        return 0.0

    # Calculate recovery time in days
    recovery_time = (first_snapshot_after_drawdown.created_at -
                     snapshots[0].created_at).days

    return recovery_time if recovery_time > 0 else 1.0
