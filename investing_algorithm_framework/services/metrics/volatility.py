"""
Volatility is a statistical measure of the dispersion of returns for a
given portfolio. In finance, it is commonly used as a proxy for risk.
This function calculates the standard deviation of daily log returns and
annualizes it, giving an estimate of how much the portfolio's value
fluctuates on a yearly basis.

| **Annual Volatility** | **Risk Level (Standalone)** | **Context Matters: Sharpe Ratio Impact** | **Comments** |
| --------------------- | --------------------------- | ---------------------------------------- | ----------- |
| **< 5%** | Very Low Risk | Sharpe > 2.0 = Excellent<br>Sharpe < 0.5 = Poor | Low volatility is great unless returns are negative |
| **5% – 10%** | Low Risk | Sharpe > 1.0 = Good<br>Sharpe < 0.3 = Mediocre | Typical for conservative portfolios |
| **10% – 15%** | Moderate Risk | Sharpe > 0.8 = Good<br>Sharpe < 0.2 = Risky | S&P 500 benchmark; quality matters |
| **15% – 25%** | High Risk | Sharpe > 0.6 = Acceptable<br>Sharpe < 0.0 = Avoid | **Example: 30% CAGR + 23% vol = Sharpe ~1.3 = Excellent** |
| **> 25%** | Very High Risk | Sharpe > 0.4 = Maybe acceptable<br>Sharpe < 0.0 = Dangerous | Only viable with strong positive returns |


Key takeaway: Don't interpret volatility in isolation. Always calculate
and compare the Sharpe Ratio to assess true strategy quality.
Your 30% CAGR with 23% volatility is exceptional because the return far outweighs the risk taken.

"""

from typing import List

import pandas as pd
import numpy as np

from investing_algorithm_framework.domain import PortfolioSnapshot


def get_annual_volatility(
    snapshots: List[PortfolioSnapshot],
    trading_days_per_year=365
) -> float:
    """
    Calculate the annualized volatility of portfolio net values.

    !Important Note:

    Volatility measures variability, not direction. For example:

    A standard deviation of 0.238 (23.8%) means returns swing
    wildly around their average, but it doesn't tell you if that average
    is positive or negative.

    Two scenarios with the same 23.8% volatility:
        Mean return = +15% per year, Std = 23.8%
        16% chance of losing >8.8% (15% - 23.8%)
        16% chance of gaining >38.8% (15% + 23.8%)
        This is excellent — high growth with swings

        Mean return = -5% per year, Std = 23.8%
        16% chance of losing >28.8% (-5% - 23.8%)
        16% chance of gaining >18.8% (-5% + 23.8%)
        This is terrible — losing money with high risk

    To assess if "always good returns with high std" is perfect, you need
    to consider risk-adjusted metrics like the Sharpe Ratio:
    Sharpe Ratio = (Mean Return - Risk-Free Rate) / Volatility
    Higher is better; tells you return per unit of risk taken

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots
            from the backtest report.
        trading_days_per_year (int): Number of trading days in a year.

    Returns:
        Float: Annualized volatility as a float
    """

    if len(snapshots) < 2:
        return 0.0

    # Build DataFrame from snapshots
    records = [
        (snapshot.total_value, snapshot.created_at) for snapshot in snapshots
    ]
    df = pd.DataFrame(records, columns=['total_value', 'created_at'])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.set_index('created_at').sort_index().drop_duplicates()

    # Resample to daily frequency, taking the last value of each day
    df_daily = df.resample('D').last()
    df_daily = df_daily.dropna()

    if len(df_daily) < 2:
        return 0.0

    # Calculate log returns on daily data
    df_daily['log_return'] = np.log(df_daily['total_value'] / df_daily['total_value'].shift(1))
    df_daily = df_daily.dropna()

    # Calculate daily volatility (standard deviation of daily returns)
    daily_volatility = df_daily['log_return'].std()

    # Annualize using trading days per year
    return daily_volatility * np.sqrt(trading_days_per_year)
