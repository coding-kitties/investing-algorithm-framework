from typing import Optional

import pandas as pd
import yfinance as yf

from investing_algorithm_framework.domain.models import TradeStatus


def get_sharpe_ratio(
    backtest_report,
    region: str = 'us',
    risk_free_rate: Optional[float] = None,
    frequency: str = 'weekly'  # 'daily' or 'weekly'
) -> float:
    """
    Calculate the Sharpe Ratio from a backtest report using daily or
    weekly returns.

    The Sharpe Ratio is calculated as:
        (Annualized Return - Risk-Free Rate) / Annualized Std Dev of Returns

    Args:
        backtest_report: Object with get_trades(trade_status=...) and
            `number_of_days` attributes.
        region (str): Used to fetch the default risk-free rate if not
            provided. Defaults to 'us'. 'eu' for Europe, 'us' for the
            United States.
        risk_free_rate (float, optional): Annual risk-free rate as a
            decimal (e.g., 0.047 for 4.7%).
        frequency (str): Either 'daily' or 'weekly', determines return
            interval.

    Returns:
        float: The Sharpe Ratio.
    """
    if risk_free_rate is None:
        if region.lower() == 'us':
            risk_free_rate = get_risk_free_rate_us()
        else:
            raise ValueError(f"Unsupported region: {region}")

    trades = backtest_report.get_trades(trade_status=TradeStatus.CLOSED)
    if not trades:
        return 0.0

    data = [(trade.closed_at, trade.net_gain) for trade in trades]
    df = pd.DataFrame(data, columns=['timestamp', 'net_gain'])
    df.set_index('timestamp', inplace=True)

    # Resample net gains
    if frequency == 'weekly':
        returns = df['net_gain'].resample('W').sum()
    elif frequency == 'daily':
        returns = df['net_gain'].resample('D').sum()
    else:
        raise ValueError("frequency must be 'daily' or 'weekly'")

    returns = returns[returns != 0]
    if len(returns) < 2:
        return 0.0

    duration_years = backtest_report.number_of_days / 365.25

    total_return = returns.sum()
    annualized_return = total_return / duration_years

    std_dev = returns.std()
    annualized_std = std_dev * (len(returns) ** 0.5) / duration_years ** 0.5

    if annualized_std == 0:
        return 0.0

    sharpe_ratio = (annualized_return - risk_free_rate) / annualized_std
    return sharpe_ratio


def get_risk_free_rate_us():
    ten_year = yf.Ticker("^TNX")
    hist = ten_year.history(period="5d")
    latest_yield = hist["Close"].iloc[-1] / 100
    return latest_yield
