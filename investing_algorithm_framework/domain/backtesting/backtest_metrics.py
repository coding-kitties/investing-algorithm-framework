import os
from pathlib import Path
from dataclasses import dataclass, field
from logging import getLogger
from typing import Tuple, List
from datetime import datetime, date
import json
import pandas as pd

from investing_algorithm_framework.domain.models import Trade


logger = getLogger(__name__)


@dataclass
class BacktestMetrics:
    """
    Represents the result of a backtest, including metrics such as
    total return, annualized return, volatility, Sharpe ratio,
    and maximum drawdown.

    Attributes:
        backtest_start_date (datetime): The start date of the backtest.
        backtest_end_date (datetime): The end date of the backtest.
        equity_curve (List[Tuple[datetime, float]]): A list of
            tuples representing  the equity curve, where each tuple
            contains a date and the  corresponding portfolio value.
        growth (float): The growth of the portfolio over the backtest period.
        growth_percentage (float): The percentage growth of the portfolio
            over the backtest period.
        final_value (float): The final value of the portfolio at the end
            of the backtest.
        total_net_gain (float): The total return of the backtest.
        total_net_gain_percentage (float): The total return percentage
        total_loss (float): The total loss of the backtest.
        cagr (float): The compound annual growth rate of the backtest.
        sharpe_ratio (float): The Sharpe ratio of the backtest, indicating
            risk-adjusted return.
        rolling_sharpe_ratio (List[Tuple[datetime, float]): A list of rolling
            Sharpe ratios over the backtest period.
        sortino_ratio (float): The Sortino ratio of the backtest, focusing
            on downside risk.
        calmar_ratio (float): The Calmar ratio of the backtest, comparing
            CAGR to maximum drawdown.
        profit_factor (float): The profit factor of the backtest, calculated
            as total profit divided by total loss.
        annual_volatility (float): The annualized volatility of the
            portfolio returns.
        monthly_returns (List[Tuple[datetime, float]]): A list of monthly
            returns during the backtest.
        yearly_returns (List[Tuple[datetime, float]]): A list of yearly returns
            during the backtest.
        drawdown_series (List[Tuple[datetime, float]]): A list of drawdown
            values over the backtest period.
        max_drawdown (float): The maximum drawdown observed during
            the backtest.
        max_drawdown_absolute (float): The maximum absolute drawdown
            observed during the backtest.
        max_daily_drawdown (float): The maximum daily drawdown
            observed during the backtest.
        max_drawdown_duration (int): The duration of the maximum
            drawdown in days.
        trades_per_year (float): The average number of trades
            executed per year.
        trade_per_day (float): The average number of trades executed per day.
        exposure_ratio (float): The exposure ratio, indicating the
            average exposure of the portfolio.
        cumulative_exposure (float): The cumulative exposure, indicating the
            total exposure of the portfolio over the backtest period.
        trades_average_gain (float): The average gain from winning trades.
        trades_average_gain_percentage (float): The average gain percentage
            from winning trades.
        trades_average_loss (float): The average loss from losing trades.
        trades_average_loss_percentage (float): The average loss percentage
            from losing trades.
        trades_average_return (float): The average return from all trades.
        trades_average_return_percentage (float): The average return
            percentage from all trades.
        best_trade (float): A string representation of the best trade,
            including net gain and percentage.
        worst_trade (float): A string representation of the worst trade,
            including net loss and percentage.
        average_trade_duration (float): The average duration of
            trades in hours.
        number_of_trades (int): The total number of trades executed
            during the backtest.
        win_rate (float): The win rate of the trades, expressed
            as a percentage.
        win_loss_ratio (float): The ratio of winning trades
            to losing trades.
        percentage_winning_months (float): The percentage of months
            with positive returns.
        percentage_winning_years (float): The percentage of years with
            positive returns.
        percentage_positive_trades (float): The percentage of trades that
            were profitable.
        percentage_negative_trades (float): The percentage of trades that
            were unprofitable.
        average_monthly_return (float): The average monthly return
            of the portfolio.
        average_monthly_return_losing_months (float): The average monthly
            return during losing months.
        average_monthly_return_winning_months (float): The average monthly
            return during winning months.
        best_month (datetime): A string representation of the best month,
            including return and date.
        best_year (datetime): A string representation of the best year,
            including return and date.
        worst_month (datetime): A string representation of the worst month,
            including return and date.
        worst_year (datetime): A string representation of the worst year,
            including return and date.
    """
    backtest_start_date: datetime
    backtest_end_date: datetime
    equity_curve: List[Tuple[float, datetime]] = field(default_factory=list)
    growth: float = 0.0
    growth_percentage: float = 0.0
    total_net_gain: float = 0.0
    total_net_gain_percentage: float = 0.0
    final_value: float = 0.0
    cagr: float = 0.0
    sharpe_ratio: float = 0.0
    rolling_sharpe_ratio: List[Tuple[float, datetime]] = \
        field(default_factory=list)
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    profit_factor: float = 0.0
    gross_profit: float = None
    gross_loss: float = None
    annual_volatility: float = 0.0
    monthly_returns: List[Tuple[float, datetime]] = field(default_factory=list)
    yearly_returns: List[Tuple[float, date]] = field(default_factory=list)
    drawdown_series: List[Tuple[float, datetime]] = field(default_factory=list)
    max_drawdown: float = 0.0
    max_drawdown_absolute: float = 0.0
    max_daily_drawdown: float = 0.0
    max_drawdown_duration: int = 0
    trades_per_year: float = 0.0
    trade_per_day: float = 0.0
    exposure_ratio: float = 0.0
    cumulative_exposure: float = 0.0
    trades_average_gain: float = 0.0
    trades_average_gain_percentage: float = 0.0
    trades_average_loss: float = 0.0
    trades_average_loss_percentage: float = 0.0
    trades_average_return: float = 0.0
    trades_average_return_percentage: float = 0.0
    best_trade: Trade = None
    worst_trade: Trade = None
    average_trade_duration: float = 0.0
    average_trade_size: float = 0.0
    number_of_trades: int = 0
    win_rate: float = 0.0
    win_loss_ratio: float = 0.0
    percentage_positive_trades: float = 0.0
    percentage_negative_trades: float = 0.0
    percentage_winning_months: float = 0.0
    percentage_winning_years: float = 0.0
    average_monthly_return: float = 0.0
    average_monthly_return_losing_months: float = 0.0
    average_monthly_return_winning_months: float = 0.0
    best_month: Tuple[float, datetime] = None
    best_year: Tuple[float, date] = None
    worst_month: Tuple[float, datetime] = None
    worst_year: Tuple[float, date] = None

    def to_dict(self) -> dict:
        """
        Convert the BacktestMetrics instance to a dictionary.

        Returns:
            dict: A dictionary representation of the BacktestMetrics instance.
        """
        return {
            "backtest_start_date": self.backtest_start_date.isoformat(),
            "backtest_end_date": self.backtest_end_date.isoformat(),
            "equity_curve": [(value, date.isoformat())
                             for value, date in self.equity_curve],
            "total_net_gain": self.total_net_gain,
            "total_net_gain_percentage": self.total_net_gain_percentage,
            "final_value": self.final_value,
            "cagr": self.cagr,
            "sharpe_ratio": self.sharpe_ratio,
            "rolling_sharpe_ratio": [
                (value, date.isoformat())
                for value, date in self.rolling_sharpe_ratio
            ],
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "profit_factor": self.profit_factor,
            "gross_profit": self.gross_profit,
            "gross_loss": self.gross_loss,
            "annual_volatility": self.annual_volatility,
            "monthly_returns": [(value, date.isoformat())
                                for value, date in self.monthly_returns],
            "yearly_returns": [(value, date.isoformat())
                               for value, date in self.yearly_returns],
            "drawdown_series": [(value, date.isoformat())
                                for value, date in self.drawdown_series],
            "max_drawdown": self.max_drawdown,
            "max_drawdown_absolute": self.max_drawdown_absolute,
            "max_daily_drawdown": self.max_daily_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "trades_per_year": self.trades_per_year,
            "trade_per_day": self.trade_per_day,
            "exposure_ratio": self.exposure_ratio,
            "cumulative_exposure": self.cumulative_exposure,
            "trades_average_gain": self.trades_average_gain,
            "trades_average_gain_percentage":
                self.trades_average_gain_percentage,
            "trades_average_loss": self.trades_average_loss,
            "trades_average_loss_percentage":
                self.trades_average_loss_percentage,
            "trades_average_return": self.trades_average_return,
            "trades_average_return_percentage":
                self.trades_average_return_percentage,
            "best_trade": self.best_trade.to_dict()
            if self.best_trade else None,
            "worst_trade": self.worst_trade.to_dict()
            if self.worst_trade else None,
            "average_trade_duration": self.average_trade_duration,
            "average_trade_size": self.average_trade_size,
            "number_of_trades": self.number_of_trades,
            "win_rate": self.win_rate,
            "win_loss_ratio": self.win_loss_ratio,
            "percentage_winning_months": self.percentage_winning_months,
            "percentage_winning_years": self.percentage_winning_years,
            "percentage_positive_trades": self.percentage_positive_trades,
            "percentage_negative_trades": self.percentage_negative_trades,
            "average_monthly_return": self.average_monthly_return,
            "average_monthly_return_losing_months":
                self.average_monthly_return_losing_months,
            "average_monthly_return_winning_months":
                self.average_monthly_return_winning_months,
            "best_month": self.best_month,
            "best_year": self.best_year,
            "worst_month": self.worst_month,
            "worst_year": self.worst_year
        }

    def save(self, file_path: str | Path) -> None:
        """
        Save the backtest metrics to a file in JSON format. The metrics will
        always be saved in a file named `metrics.json`

        Args:
            file_path (str): The directory where the metrics
            file will be saved.
        """
        with open(file_path, 'w') as file:
            json.dump(self.to_dict(), file, indent=4, default=str)

    @staticmethod
    def _parse_tuple_list_datetime(
        data: List[List]
    ) -> List[Tuple[float, datetime]]:
        """
            Parse a list of [value, datetime_string]
            into List[Tuple[float, datetime]]
        """
        return [
            (float(value), datetime.fromisoformat(date_str))
            for value, date_str in data
        ]

    @staticmethod
    def _parse_tuple_list_date(data: List[List]) -> List[Tuple[float, date]]:
        """
        Parse a list of [value, date_string] into List[Tuple[float, date]]
        """
        return [
            (float(value), datetime.fromisoformat(date_str).date())
            for value, date_str in data
        ]

    @staticmethod
    def _parse_tuple_datetime(data) -> Tuple[float, datetime]:
        """Parse a [value, datetime_string] into Tuple[float, datetime]"""
        if data is None:
            return None, None

        # Check if the value is NaN or None
        if pd.isna(data[0]) or data[0] is None:
            value = pd.NA
        else:
            value = float(data[0])

        # Parse the datetime string
        if data[1] is None or pd.isna(data[1]):
            value = None
        else:
            # Convert the string to a datetime object
            date = datetime.fromisoformat(data[1])

        return (value, date)

    @staticmethod
    def _parse_tuple_date(data) -> Tuple[float, date]:
        """Parse a [value, date_string] into Tuple[float, date]"""
        if data is None:
            return None, None

        # Check if the value is
        if pd.isna(data[0]) or data[0] is None:
            value = pd.NA
        else:
            value = float(data[0])

        # Parse the date string
        if data[1] is None or pd.isna(data[1]):
            date = None
        else:
            date = datetime.fromisoformat(data[1]).date()

        return (value, date)

    @staticmethod
    def open(file_path: str | Path) -> 'BacktestMetrics':
        """
        Open a backtest metrics file from a directory and
        return a BacktestMetrics instance.

        Args:
            file_path (str): The path to the metrics file.

        Returns:
            BacktestMetrics: An instance of BacktestMetrics
                loaded from the file.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Metrics file not found at {file_path}")

        with open(file_path, 'r') as file:
            data = json.load(file)

        # Parse datetime fields
        data['backtest_start_date'] = datetime.fromisoformat(
            data['backtest_start_date']
        )
        data['backtest_end_date'] = datetime.fromisoformat(
            data['backtest_end_date']
        )

        # Parse tuple lists with datetime
        data['equity_curve'] = BacktestMetrics._parse_tuple_list_datetime(
            data.get('equity_curve', [])
        )
        data['rolling_sharpe_ratio'] = BacktestMetrics\
            ._parse_tuple_list_datetime(data.get('rolling_sharpe_ratio', []))
        data['monthly_returns'] = BacktestMetrics\
            ._parse_tuple_list_datetime(data.get('monthly_returns', []))
        data['drawdown_series'] = BacktestMetrics\
            ._parse_tuple_list_datetime(data.get('drawdown_series', []))

        # Parse tuple lists with date
        data['yearly_returns'] = BacktestMetrics\
            ._parse_tuple_list_date(data.get('yearly_returns', []))

        # Parse single tuples
        data['best_month'] = BacktestMetrics\
            ._parse_tuple_datetime(data.get('best_month'))
        data['worst_month'] = BacktestMetrics\
            ._parse_tuple_datetime(data.get('worst_month'))
        data['best_year'] = BacktestMetrics\
            ._parse_tuple_date(data.get('best_year'))
        data['worst_year'] = BacktestMetrics\
            ._parse_tuple_date(data.get('worst_year'))

        # Parse Trade objects if they exist
        if data.get('best_trade'):
            data['best_trade'] = Trade.from_dict(data['best_trade'])
        if data.get('worst_trade'):
            data['worst_trade'] = Trade.from_dict(data['worst_trade'])

        return BacktestMetrics(**data)

    def __repr__(self):
        """
        Return a string representation of the Backtest instance.

        Returns:
            str: A string representation of the Backtest instance.
        """
        return json.dumps(
            self.to_dict(), indent=4, sort_keys=True, default=str
        )
