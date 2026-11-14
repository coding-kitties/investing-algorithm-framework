import json
import os
from dataclasses import dataclass
from logging import getLogger
from pathlib import Path

logger = getLogger(__name__)

AGGREGATION_SEMANTICS_VERSION = 2


@dataclass
class BacktestSummaryMetrics:
    """
    Represents statistics across independently evaluated backtest windows.

    Portfolio-level metrics are unavailable unless a single declared equity
    path is supplied. Legacy fields such as ``cagr`` and ``sharpe_ratio`` are
    retained as compatibility aliases for duration-weighted window means.

    .. note:: Field semantics & known duplicates (issue #511)

        - ``total_loss`` / ``total_loss_percentage`` are gross-loss
          based: ``total_loss`` is ``sum(per-run gross_loss)`` (a
          non-negative magnitude in account currency) and
          ``total_loss_percentage`` is ``total_loss /
          sum(initial_unallocated)`` (decimal). They no longer mix
          with net-return semantics. See B1/B2 in issue #511.

        - ``total_growth`` / ``total_growth_percentage`` are
          numerically equivalent to ``total_net_gain`` /
          ``total_net_gain_percentage`` for closed-position backtests
          because both are derived from the same start/end portfolio
          values. They are kept for backwards compatibility but should
          be considered legacy aliases. See B3 in issue #511.

        - ``average_net_gain``, ``average_loss``, ``average_growth``
          (and their ``*_percentage`` counterparts) are time-weighted
          means **across windows**. For a single-window backtest they
          collapse to the corresponding ``total_*`` value by
          definition (weighted mean of one element equals that
          element). See B4 in issue #511. For per-trade averages use
          ``average_trade_*`` instead.

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
        cagr (float): Legacy alias for
            ``duration_weighted_mean_window_cagr``.
        sharpe_ratio (float): Legacy alias for
            ``duration_weighted_mean_window_sharpe_ratio``.
        sortino_ratio (float): Legacy alias for
            ``duration_weighted_mean_window_sortino_ratio``.
        calmar_ratio (float): Legacy alias for
            ``duration_weighted_mean_window_calmar_ratio``.
        profit_factor (float): Total profit / total loss.
        annual_volatility (float): Annualized volatility of returns.
        max_drawdown (float): Legacy alias for
            ``worst_window_max_drawdown`` as a nonnegative magnitude.
        max_drawdown_duration (int): Duration of the maximum drawdown.
        trades_per_year (float): Average trades executed per year.
        win_rate (float): Percentage of winning trades.
        current_win_rate (float): Win rate over recent trades.
        win_loss_ratio (float): Ratio of average win to average loss.
        current_win_loss_ratio (float): Win/loss ratio over recent trades.
        number_of_trades (int): Total number of trades executed.
        cumulative_exposure (float): Total exposure over the backtest period.
        exposure_ratio (float): Ratio of exposure to available capital.
        number_of_windows (int): Total number of backtest windows/runs.
        number_of_profitable_windows (int): Number of windows with positive
            net gain.
        number_of_windows_with_trades (int): Number of windows with at least
            one closed trade.
    """
    aggregation_semantics_version: int = None
    aggregation_mode: str = None
    return_definition: str = None
    drawdown_definition: str = None
    window_count_expected: int = None
    window_count_evaluated: int = None
    window_count_missing: int = None
    complete: bool = None
    capital_weighted_return_unavailable_reason: str = None
    total_net_gain: float = None
    total_net_gain_percentage: float = None
    capital_weighted_window_return: float = None
    median_window_return: float = None
    worst_window_return: float = None
    best_window_return: float = None
    mean_window_duration_days: float = None
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
    duration_weighted_mean_window_cagr: float = None
    duration_weighted_mean_window_sharpe_ratio: float = None
    duration_weighted_mean_window_sortino_ratio: float = None
    duration_weighted_mean_window_calmar_ratio: float = None
    profit_factor: float = None
    annual_volatility: float = None
    duration_weighted_mean_window_annual_volatility: float = None
    max_drawdown: float = None
    worst_window_max_drawdown: float = None
    max_drawdown_duration: int = None
    portfolio_cagr: float = None
    portfolio_sharpe_ratio: float = None
    portfolio_sortino_ratio: float = None
    portfolio_calmar_ratio: float = None
    portfolio_annual_volatility: float = None
    portfolio_max_drawdown: float = None
    portfolio_var_95: float = None
    portfolio_cvar_95: float = None
    trades_per_year: float = None
    trades_per_month: float = None
    trades_per_week: float = None
    win_rate: float = None
    current_win_rate: float = None
    win_loss_ratio: float = None
    current_win_loss_ratio: float = None
    number_of_trades: int = None
    number_of_trades_closed: int = None
    cumulative_exposure: float = None
    exposure_ratio: float = None
    number_of_windows: int = None
    number_of_profitable_windows: int = None
    number_of_windows_with_trades: int = None
    var_95: float = None
    cvar_95: float = None
    average_trade_duration: float = None
    average_win_duration: float = None
    average_loss_duration: float = None
    max_consecutive_wins: int = None
    max_consecutive_losses: int = None
    return_consistency: float = None
    win_rate_consistency: float = None
    sharpe_consistency: float = None
    consistency_score: float = None
    return_stability: float = None
    win_rate_stability: float = None
    sharpe_stability: float = None
    stability_score: float = None

    def to_dict(self) -> dict:
        """
        Convert the BacktestSummaryMetrics instance to a dictionary.
        """
        return {
            "aggregation_semantics_version":
                self.aggregation_semantics_version,
            "aggregation_mode": self.aggregation_mode,
            "return_definition": self.return_definition,
            "drawdown_definition": self.drawdown_definition,
            "window_count_expected": self.window_count_expected,
            "window_count_evaluated": self.window_count_evaluated,
            "window_count_missing": self.window_count_missing,
            "complete": self.complete,
            "capital_weighted_return_unavailable_reason":
                self.capital_weighted_return_unavailable_reason,
            "total_net_gain": self.total_net_gain,
            "total_net_gain_percentage": self.total_net_gain_percentage,
            "capital_weighted_window_return":
                self.capital_weighted_window_return,
            "median_window_return": self.median_window_return,
            "worst_window_return": self.worst_window_return,
            "best_window_return": self.best_window_return,
            "mean_window_duration_days": self.mean_window_duration_days,
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
            "duration_weighted_mean_window_cagr":
                self.duration_weighted_mean_window_cagr,
            "duration_weighted_mean_window_sharpe_ratio":
                self.duration_weighted_mean_window_sharpe_ratio,
            "duration_weighted_mean_window_sortino_ratio":
                self.duration_weighted_mean_window_sortino_ratio,
            "duration_weighted_mean_window_calmar_ratio":
                self.duration_weighted_mean_window_calmar_ratio,
            "profit_factor": self.profit_factor,
            "annual_volatility": self.annual_volatility,
            "duration_weighted_mean_window_annual_volatility":
                self.duration_weighted_mean_window_annual_volatility,
            "max_drawdown": self.max_drawdown,
            "worst_window_max_drawdown": self.worst_window_max_drawdown,
            "max_drawdown_duration": self.max_drawdown_duration,
            "portfolio_cagr": self.portfolio_cagr,
            "portfolio_sharpe_ratio": self.portfolio_sharpe_ratio,
            "portfolio_sortino_ratio": self.portfolio_sortino_ratio,
            "portfolio_calmar_ratio": self.portfolio_calmar_ratio,
            "portfolio_annual_volatility": self.portfolio_annual_volatility,
            "portfolio_max_drawdown": self.portfolio_max_drawdown,
            "portfolio_var_95": self.portfolio_var_95,
            "portfolio_cvar_95": self.portfolio_cvar_95,
            "trades_per_year": self.trades_per_year,
            "trades_per_month": self.trades_per_month,
            "trades_per_week": self.trades_per_week,
            "win_rate": self.win_rate,
            "current_win_rate": self.current_win_rate,
            "win_loss_ratio": self.win_loss_ratio,
            "current_win_loss_ratio": self.current_win_loss_ratio,
            "number_of_trades": self.number_of_trades,
            "number_of_trades_closed": self.number_of_trades_closed,
            "cumulative_exposure": self.cumulative_exposure,
            "exposure_ratio": self.exposure_ratio,
            "number_of_windows": self.number_of_windows,
            "number_of_profitable_windows": self.number_of_profitable_windows,
            "number_of_windows_with_trades":
                self.number_of_windows_with_trades,
            "average_trade_duration": self.average_trade_duration,
            "average_win_duration": self.average_win_duration,
            "average_loss_duration": self.average_loss_duration,
            "var_95": self.var_95,
            "cvar_95": self.cvar_95,
            "max_consecutive_wins": self.max_consecutive_wins,
            "max_consecutive_losses": self.max_consecutive_losses,
            "return_consistency": self.return_consistency,
            "win_rate_consistency": self.win_rate_consistency,
            "sharpe_consistency": self.sharpe_consistency,
            "consistency_score": self.consistency_score,
            "return_stability": self.return_stability,
            "win_rate_stability": self.win_rate_stability,
            "sharpe_stability": self.sharpe_stability,
            "stability_score": self.stability_score,
        }

    def save(self, file_path: str | Path) -> None:
        """
        Save the summary metrics to a JSON file.
        """
        with open(file_path, 'w') as file:
            json.dump(self.to_dict(), file, indent=4, default=str)

    @classmethod
    def from_dict(cls, data: dict) -> 'BacktestSummaryMetrics':
        """Reconstruct a BacktestSummaryMetrics from a plain dict."""
        if data is None:
            return None
        return cls(**data)

    @staticmethod
    def open(file_path: str | Path) -> 'BacktestSummaryMetrics':
        """
        Load summary metrics from a JSON file.
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Metrics file not found at {file_path}")

        with open(file_path, 'r') as file:
            data = json.load(file)

        return BacktestSummaryMetrics.from_dict(data)

    def __repr__(self):
        return json.dumps(
            self.to_dict(), indent=4, sort_keys=True, default=str
        )
