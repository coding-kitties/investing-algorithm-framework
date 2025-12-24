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

import math
from datetime import datetime
from typing import List, Tuple

import numpy as np
import pandas as pd

from investing_algorithm_framework.domain import PortfolioSnapshot
from .mean_daily_return import get_mean_daily_return
from .standard_deviation import get_daily_returns_std


def get_sharpe_ratio(
    snapshots: List[PortfolioSnapshot], risk_free_rate: float,
) -> float:
    """
    Calculate the Sharpe Ratio from a backtest report using daily or
    weekly returns.

    The Sharpe Ratio is calculated as:
        (Annualized Return - Risk-Free Rate) / Annualized Std Dev of Returns

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots
        risk_free_rate (float, optional): Annual risk-free rate as a
            decimal (e.g., 0.047 for 4.7%).

    Returns:
        float: The Sharpe Ratio.
    """
    snapshots = sorted(snapshots, key=lambda s: s.created_at)
    mean_daily_return = get_mean_daily_return(snapshots)
    std_daily_return = get_daily_returns_std(snapshots)

    if std_daily_return == 0:
        return float('nan')  # Avoid division by zero

    # Formula: Sharpe Ratio = (Mean Daily Return × Periods Per Year - Risk-Free Rate) /
    # (Standard Deviation of Daily Returns × sqrt(Periods Per Year))
    return (mean_daily_return * 365 - risk_free_rate) / \
              (std_daily_return * math.sqrt(365))


def get_rolling_sharpe_ratio(
    snapshots: List[PortfolioSnapshot], risk_free_rate: float
) -> List[Tuple[float, datetime]]:
    """
    Calculate the rolling Sharpe Ratio over a 365-day window.

    Args:
        snapshots (List[PortfolioSnapshot]): Time-sorted list of snapshots.
        risk_free_rate (float): Annualized risk-free rate (e.g., 0.03 for 3%).

    Returns:
        List[Tuple[float, datetime]]: List of (sharpe_ratio, snapshot_date).
    """
    data = [(s.created_at, s.total_value) for s in snapshots]
    df = pd.DataFrame(data, columns=["created_at", "total_value"])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').drop_duplicates('created_at')\
        .set_index('created_at')

    # Resample to daily frequency using last value of the day
    daily_df = df.resample('1D').last().dropna()

    # Returns as percentage change
    returns_s = daily_df['total_value'].pct_change().dropna()

    # Rolling Annualised Sharpe
    rolling = returns_s.rolling(window=365)
    rolling_sharpe_s = np.sqrt(365) * (
        rolling.mean() / rolling.std()
    )

    # Ensure chronological order
    snapshots = sorted(snapshots, key=lambda s: s.created_at)

    result = []
    for date, sharpe in rolling_sharpe_s.items():

        if pd.isna(sharpe):
            result.append((sharpe, date))
            continue

        # Find the corresponding snapshot
        snapshot = next((s for s in snapshots if s.created_at == date), None)

        if snapshot:
            result.append((sharpe, snapshot.created_at))

    return result
