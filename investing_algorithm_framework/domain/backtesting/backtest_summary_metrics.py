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
        gross_loss (float): Total gross loss from all trades.
        growth (float): Total growth from the backtest.
        growth_percentage (float): Total growth percentage from the backtest.
        trades_average_return (float): Average return per trade.
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
    gross_loss: float = None
    growth: float = None
    growth_percentage: float = None
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
            "gross_loss": self.gross_loss,
            "growth": self.growth,
            "growth_percentage": self.growth_percentage,
            "trades_average_return": self.trades_average_return,
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
                self.cumulative_exposure, other.cumulative_exposure
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
            self.total_net_gain = safe_mean(
                self.total_net_gain, other.total_net_gain
            )

        if self.total_net_gain_percentage is None:
            self.total_net_gain_percentage = other.total_net_gain_percentage
        else:
            self.total_net_gain_percentage = safe_mean(
                self.total_net_gain_percentage, other.total_net_gain_percentage
            )

        if self.gross_loss is None:
            self.gross_loss = other.gross_loss
        else:
            self.gross_loss = safe_mean(self.gross_loss, other.gross_loss)

        if self.growth is None:
            self.growth = other.growth
        else:
            self.growth = safe_mean(self.growth, other.growth)

        if self.growth_percentage is None:
            self.growth_percentage = other.growth_percentage
        else:
            self.growth_percentage = safe_mean(
                self.growth_percentage, other.growth_percentage
            )

        if self.trades_average_return is None:
            self.trades_average_return = other.trades_average_return
        else:
            self.trades_average_return = safe_mean(
                self.trades_average_return, other.trades_average_return
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

    def __repr__(self):
        return json.dumps(
            self.to_dict(), indent=4, sort_keys=True, default=str
        )
