"""
The Sharpe Ratio is a widely used risk-adjusted performance metric. It
measures the excess return per unit of risk (volatility), where risk is
represented by the standard deviation of returns.

| Sharpe Ratio   | Interpretation                              |
| -------------- | ------------------------------------------- |
| **< 0**        | Bad: Underperforms risk-free asset          |
| **0.0 – 1.0**  | Suboptimal: Returns do not justify risk     |
| **1.0 – 1.99** | Acceptable: Reasonable risk-adjusted return |
| **2.0 – 2.99** | Good: Strong risk-adjusted performance      |
| **3.0+**       | Excellent: Exceptional risk-adjusted return |

Sharpe Ratio is highly sensitive to the volatility estimate: Inconsistent sampling frequency, short backtests, or low trade frequency can distort it.

Different strategies have different risk profiles:

High-frequency strategies may have high Sharpe Ratios (>3).

Trend-following strategies might have lower Sharpe (1–2) but strong CAGR and Calmar.

Use risk-free rate (~4–5% annual currently) if your backtest spans long periods.

### 📌 Practical Notes about the implementation:

- Use **daily returns** for consistent Sharpe Ratio calculation and **annualize** the result using this formula:


Sharpe Ratio Formula:
    Sharpe Ratio = (Mean Daily Return × Periods Per Year - Risk-Free Rate) /
                   (Standard Deviation of Daily Returns × sqrt(Periods Per Year))

- You can also calculate a **rolling Sharpe Ratio** (e.g., over a 90-day window) to detect changes in performance stability over time.

Mean daily return is either based on the real returns from the backtest or the CAGR, depending on the data duration.

When do we use actual returns vs CAGR?

| Data Duration | Use This Approach                                               | Reason                                                            |
| ------------- | --------------------------------------------------------------- | ----------------------------------------------------------------- |
| **< 1 year**  | Use **CAGR** directly and avoid Sharpe Ratio                    | Not enough data to estimate volatility robustly                   |
| **1–2 years** | Use **CAGR + conservative vol estimate** OR Sharpe with caution | Sharpe may be unstable, consider adding error bars or disclaimers |
| **> 2 years** | Use **Sharpe Ratio** based on periodic returns                  | Adequate data to reliably estimate risk-adjusted return           |

"""

from typing import Optional

import math

from investing_algorithm_framework.domain.models import BacktestReport
from .mean_daily_return import get_mean_daily_return
from .risk_free_rate import get_risk_free_rate_us
from .standard_deviation import get_daily_returns_std


def get_sharpe_ratio(
    backtest_report: BacktestReport, risk_free_rate: Optional[float] = None,
) -> float:
    """
    Calculate the Sharpe Ratio from a backtest report using daily or
    weekly returns.

    The Sharpe Ratio is calculated as:
        (Annualized Return - Risk-Free Rate) / Annualized Std Dev of Returns

    Args:
        backtest_report: Object with get_trades(trade_status=...) and
            `number_of_days` attributes.
        risk_free_rate (float, optional): Annual risk-free rate as a
            decimal (e.g., 0.047 for 4.7%).

    Returns:
        float: The Sharpe Ratio.
    """
    snapshots = backtest_report.get_snapshots()
    snapshots = sorted(snapshots, key=lambda s: s.created_at)
    mean_daily_return = get_mean_daily_return(backtest_report)
    std_daily_return = get_daily_returns_std(snapshots)

    if risk_free_rate is None:
        risk_free_rate = get_risk_free_rate_us()

    # Formula: Sharpe Ratio = (Mean Daily Return × Periods Per Year - Risk-Free Rate) /
    # (Standard Deviation of Daily Returns × sqrt(Periods Per Year))
    return (mean_daily_return * 365 - risk_free_rate) / \
              (std_daily_return * math.sqrt(365))
