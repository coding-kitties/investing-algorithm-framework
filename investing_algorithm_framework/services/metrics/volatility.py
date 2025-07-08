"""
Volatility is a statistical measure of the dispersion of returns for a
given portfolio. In finance, it is commonly used as a proxy for risk.
This function calculates the standard deviation of daily log returns and
annualizes it, giving an estimate of how much the portfolio's value
fluctuates on a yearly basis.

| **Annual Volatility** | **Risk Level** | **Typical for...**                                                     | **Comments**                                                                    |
| --------------------- | -------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| **< 5%**              | Very Low Risk  | Cash equivalents, short-term bonds                                     | Low return expectations; often used for capital preservation                    |
| **5% – 10%**          | Low Risk       | Diversified bond portfolios, conservative allocation strategies        | Suitable for risk-averse investors                                              |
| **10% – 15%**         | Moderate Risk  | Balanced portfolios, large-cap equity indexes (e.g., S\&P 500 ≈ \~15%) | Standard for traditional diversified portfolios                                 |
| **15% – 25%**         | High Risk      | Growth stocks, hedge funds, active equity strategies                   | Higher return potential, but more drawdowns                                     |
| **> 25%**             | Very High Risk | Crypto, leveraged ETFs, speculative strategies                         | High potential returns, but prone to large losses; often not suitable long-term |

"""

from typing import List

import pandas as pd
import numpy as np

from investing_algorithm_framework.domain import PortfolioSnapshot


def get_annual_volatility(snapshots: List[PortfolioSnapshot]) -> float:
    """
    Calculate the annualized volatility of portfolio net values.

    Args:
        snapshots (List[PortfolioSnapshot]): List of portfolio snapshots
            from the backtest report.

    Returns:
        Float: Annualized volatility as a float
    """

    if len(snapshots) < 2:
        return 0.0  # Not enough data to calculate volatility

    # Build DataFrame from snapshots
    records = [
        (snapshot.total_value, snapshot.created_at) for snapshot in snapshots
    ]
    df = pd.DataFrame(records, columns=['total_value', 'created_at'])
    df['created_at'] = pd.to_datetime(df['created_at'])
    df = df.sort_values('created_at').drop_duplicates('created_at').copy()

    # Calculate log returns
    df['log_return'] = np.log(df['total_value'] / df['total_value'].shift(1))
    df = df.dropna()

    if df.empty:
        return 0.0

    daily_volatility = df['log_return'].std()

    start_date = snapshots[0].created_at
    end_date = snapshots[-1].created_at
    # Estimate trading days per year based on snapshot frequency
    total_days = (end_date - start_date).days
    num_observations = len(df)

    if total_days > 0:
        trading_days_per_year = (num_observations / total_days) * 365
    else:
        trading_days_per_year = 365  # Default fallback

    return daily_volatility * np.sqrt(trading_days_per_year)
