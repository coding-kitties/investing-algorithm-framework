import json
import os
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path

logger = getLogger(__name__)


@dataclass
class BacktestSummaryMetrics:
    """
    Represents the summarized results of a backtest,
    focusing on key headline performance and risk metrics.

    Attributes:
        total_net_gain (float): Total net gain from the backtest.
        total_net_gain_percentage (float): Total net gain percentage
            from the backtest.
        total_loss (float): Total gross loss from all trades.
        total_loss_percentage (float): Total gross loss percentage.
        total_growth (float): Total growth from the backtest.
        total_growth_percentage (float): Total growth percentage
            from the backtest.
        average_net_gain (float): Average returns across multiple backtests.
        average_net_gain_percentage (float): Average return percentage across
            multiple backtests.
        average_growth (float): Average growth across multiple backtests.
        average_growth_percentage (float): Average growth percentage across
            multiple backtests.
        average_loss (float): Average loss across multiple backtests.
        average_loss_percentage (float): Average loss percentage across
            multiple backtests.
        average_trade_return (float): Average return per trade.
        average_trade_return_percentage (float): Average return percentage
            per trade.
        average_trade_loss (float): Total gross loss from all trades.
        average_trade_loss_percentage (float): Average trade loss percentage.
        average_trade_gain (float): Average gain from winning trades.
        average_trade_gain_percentage (float): Average gain percentage
        cagr (float): Compound annual growth rate of the backtest.
        sharpe_ratio (float): Sharpe ratio, risk-adjusted return.
        sortino_ratio (float): Sortino ratio, downside-risk adjusted return.
        calmar_ratio (float): CAGR relative to max drawdown.
        profit_factor (float): Total profit / total loss.
        annual_volatility (float): Annualized volatility of returns.
        max_drawdown (float): Maximum drawdown observed.
        max_drawdown_duration (int): Duration of the maximum drawdown.
        trades_per_year (float): Average trades executed per year.
        win_rate (float): Percentage of winning trades.
        current_win_rate (float): Win rate over recent trades.
        win_loss_ratio (float): Ratio of average win to average loss.
        current_win_loss_ratio (float): Win/loss ratio over recent trades.
        number_of_trades (int): Total number of trades executed.
        cumulative_exposure (float): Total exposure over the backtest period.
        exposure_ratio (float): Ratio of exposure to available capital.
    """
    total_net_gain: float = None
    total_net_gain_percentage: float = None
    total_growth: float = None
    total_growth_percentage: float = None
    total_loss: float = None
    total_loss_percentage: float = None
    average_net_gain: float = None
    average_net_gain_percentage: float = None
    average_growth: float = None
    average_growth_percentage: float = None
    average_loss: float = None
    average_loss_percentage: float = None
    average_trade_return: float = None
    average_trade_return_percentage: float = None
    average_trade_loss: float = None
    average_trade_loss_percentage: float = None
    average_trade_gain: float = None
    average_trade_gain_percentage: float = None
    cagr: float = None
    sharpe_ratio: float = None
    sortino_ratio: float = None
    calmar_ratio: float = None
    profit_factor: float = None
    annual_volatility: float = None
    max_drawdown: float = None
    max_drawdown_duration: int = None
    trades_per_year: float = None
    win_rate: float = None
    current_win_rate: float = None
    win_loss_ratio: float = None
    current_win_loss_ratio: float = None
    number_of_trades: int = None
    number_of_trades_closed: int = None
    cumulative_exposure: float = None
    exposure_ratio: float = None

    def to_dict(self) -> dict:
        """
        Convert the BacktestSummaryMetrics instance to a dictionary.
        """
        return {
            "total_net_gain": self.total_net_gain,
            "total_net_gain_percentage": self.total_net_gain_percentage,
            "total_growth": self.total_growth,
            "total_growth_percentage": self.total_growth_percentage,
            "total_loss": self.total_loss,
            "total_loss_percentage": self.total_loss_percentage,
            "average_loss": self.average_loss,
            "average_loss_percentage": self.average_loss_percentage,
            "average_net_gain": self.average_net_gain,
            "average_net_gain_percentage": self.average_net_gain_percentage,
            "average_growth": self.average_growth,
            "average_growth_percentage": self.average_growth_percentage,
            "average_trade_return": self.average_trade_return,
            "average_trade_return_percentage":
                self.average_trade_return_percentage,
            "average_trade_loss": self.average_trade_loss,
            "average_trade_loss_percentage":
                self.average_trade_loss_percentage,
            "average_trade_gain": self.average_trade_gain,
            "average_trade_gain_percentage":
                self.average_trade_gain_percentage,
            "cagr": self.cagr,
            "sharpe_ratio": self.sharpe_ratio,
            "sortino_ratio": self.sortino_ratio,
            "calmar_ratio": self.calmar_ratio,
            "profit_factor": self.profit_factor,
            "annual_volatility": self.annual_volatility,
            "max_drawdown": self.max_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "trades_per_year": self.trades_per_year,
            "win_rate": self.win_rate,
            "current_win_rate": self.current_win_rate,
            "win_loss_ratio": self.win_loss_ratio,
            "current_win_loss_ratio": self.current_win_loss_ratio,
            "number_of_trades": self.number_of_trades,
            "number_of_trades_closed": self.number_of_trades_closed,
            "cumulative_exposure": self.cumulative_exposure,
            "exposure_ratio": self.exposure_ratio,
        }

    def save(self, file_path: str | Path) -> None:
        """
        Save the summary metrics to a JSON file.
        """
        with open(file_path, 'w') as file:
            json.dump(self.to_dict(), file, indent=4, default=str)

    @staticmethod
    def open(file_path: str | Path) -> 'BacktestSummaryMetrics':
        """
        Load summary metrics from a JSON file.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Metrics file not found at {file_path}")

        with open(file_path, 'r') as file:
            data = json.load(file)

        return BacktestSummaryMetrics(**data)

    def __repr__(self):
        return json.dumps(
            self.to_dict(), indent=4, sort_keys=True, default=str
        )
