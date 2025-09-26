import os
from pathlib import Path
from dataclasses import dataclass
from logging import getLogger
import json
from statistics import mean

from .backtest_metrics import BacktestMetrics

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
        win_loss_ratio (float): Ratio of average win to average loss.
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
    average_trade_return: float = None
    average_trade_return_percentage: float = None
    average_trade_loss: float = None
    average_trade_loss_percentage: float = None
    average_trade_gain: float = None
    average_trade_gain_percentage: float = None
    trades_average_return: float = None
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
    win_loss_ratio: float = None
    number_of_trades: int = None
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
            "win_loss_ratio": self.win_loss_ratio,
            "number_of_trades": self.number_of_trades,
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

    def add(self, other: BacktestMetrics) -> None:
        """
        Update this summary with another BacktestMetrics.
        Averages ratios, sums trade counts, and takes worst drawdowns.
        """
        def safe_mean(a, b):
            vals = [v for v in [a, b] if v is not None]
            return mean(vals) if vals else 0.0

        if self.cumulative_exposure is None:
            self.cumulative_exposure = other.cumulative_exposure
        else:
            self.cumulative_exposure = safe_mean(
                self.cumulative_exposure,
                other.cumulative_exposure
            )

        if self.exposure_ratio is None:
            self.exposure_ratio = other.exposure_ratio
        else:
            self.exposure_ratio = safe_mean(
                self.exposure_ratio, other.exposure_ratio
            )

        if self.total_net_gain is None:
            self.total_net_gain = other.total_net_gain
        else:
            self.total_net_gain += other.total_net_gain

        if self.total_net_gain_percentage is None:
            self.total_net_gain_percentage = other.total_net_gain_percentage
        else:
            self.total_net_gain_percentage = safe_mean(
                self.total_net_gain_percentage, other.total_net_gain_percentage
            )

        if self.total_loss is None:
            self.total_loss = other.total_loss
        else:
            self.total_loss = safe_mean(self.total_loss, other.total_loss)

        if self.total_growth is None:
            self.total_growth = other.total_growth
        else:
            self.total_growth = safe_mean(
                self.total_growth, other.total_growth
            )

        if self.total_growth_percentage is None:
            self.total_growth_percentage = other.total_growth_percentage
        else:
            self.total_growth_percentage = safe_mean(
                self.total_growth_percentage, other.total_growth_percentage
            )

        if self.average_trade_return is None:
            self.average_trade_return = other.average_trade_return
        else:
            self.average_trade_return = safe_mean(
                self.average_trade_return, other.average_trade_return
            )

        if self.average_trade_return_percentage is None:
            self.average_trade_return_percentage = \
                other.average_trade_return_percentage
        else:
            self.average_trade_return_percentage = safe_mean(
                self.average_trade_return_percentage,
                other.average_trade_return_percentage
            )

        if self.average_trade_loss is None:
            self.average_trade_loss = other.average_trade_loss
        else:
            self.average_trade_loss = safe_mean(
                self.average_trade_loss, other.average_trade_loss
            )

        if self.average_trade_loss_percentage is None:
            self.average_trade_loss_percentage = \
                other.average_trade_loss_percentage
        else:
            self.average_trade_loss_percentage = safe_mean(
                self.average_trade_loss_percentage,
                other.average_trade_loss_percentage
            )

        if self.average_trade_gain is None:
            self.average_trade_gain = other.average_trade_gain
        else:
            self.average_trade_gain = safe_mean(
                self.average_trade_gain, other.average_trade_gain
            )

        if self.average_trade_gain_percentage is None:
            self.average_trade_gain_percentage = \
                other.average_trade_gain_percentage
        else:
            self.average_trade_gain_percentage = safe_mean(
                self.average_trade_gain_percentage,
                other.average_trade_gain_percentage
            )

        if self.cagr is None:
            self.cagr = other.cagr
        else:
            self.cagr = safe_mean(self.cagr, other.cagr)

        if self.sharpe_ratio is None:
            self.sharpe_ratio = other.sharpe_ratio
        else:
            self.sharpe_ratio = safe_mean(
                self.sharpe_ratio, other.sharpe_ratio
            )

        if self.sortino_ratio is None:
            self.sortino_ratio = other.sortino_ratio
        else:
            self.sortino_ratio = safe_mean(
                self.sortino_ratio, other.sortino_ratio
            )

        if self.calmar_ratio is None:
            self.calmar_ratio = other.calmar_ratio
        else:
            self.calmar_ratio = safe_mean(
                self.calmar_ratio, other.calmar_ratio
            )

        if self.profit_factor is None:
            self.profit_factor = other.profit_factor
        else:
            self.profit_factor = safe_mean(
                self.profit_factor, other.profit_factor
            )

        if self.annual_volatility is None:
            self.annual_volatility = other.annual_volatility
        else:
            self.annual_volatility = safe_mean(
                self.annual_volatility, other.annual_volatility
            )

        if self.max_drawdown is None:
            self.max_drawdown = other.max_drawdown
        else:
            self.max_drawdown = min(self.max_drawdown, other.max_drawdown)

        if self.max_drawdown_duration is None:
            self.max_drawdown_duration = other.max_drawdown_duration
        else:
            self.max_drawdown_duration = max(
                self.max_drawdown_duration, other.max_drawdown_duration
            )

        if self.trades_per_year is None:
            self.trades_per_year = other.trades_per_year
        else:
            self.trades_per_year = safe_mean(
                self.trades_per_year, other.trades_per_year
            )

        if self.win_rate is None:
            self.win_rate = other.win_rate
        else:
            self.win_rate = safe_mean(self.win_rate, other.win_rate)

        if self.win_loss_ratio is None:
            self.win_loss_ratio = other.win_loss_ratio
        else:
            self.win_loss_ratio = safe_mean(
                self.win_loss_ratio, other.win_loss_ratio
            )

        if self.number_of_trades is None:
            self.number_of_trades = other.number_of_trades
        else:
            self.number_of_trades += other.number_of_trades

        if self.average_net_gain is None:
            self.average_net_gain = other.total_net_gain
        else:
            self.average_net_gain = safe_mean(
                self.average_net_gain, other.total_net_gain
            )

        if self.average_net_gain_percentage is None:
            self.average_net_gain_percentage = other.total_net_gain_percentage
        else:
            self.average_net_gain_percentage = safe_mean(
                self.average_net_gain_percentage,
                other.total_net_gain_percentage
            )

        if self.average_growth is None:
            self.average_growth = other.total_growth
        else:
            self.average_growth = safe_mean(
                self.average_growth, other.total_growth
            )

        if self.average_growth_percentage is None:
            self.average_growth_percentage = other.total_growth_percentage
        else:
            self.average_growth_percentage = safe_mean(
                self.average_growth_percentage,
                other.total_growth_percentage
            )

    def __repr__(self):
        return json.dumps(
            self.to_dict(), indent=4, sort_keys=True, default=str
        )
