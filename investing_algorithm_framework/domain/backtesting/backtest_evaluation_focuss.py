from enum import Enum


class BacktestEvaluationFocus(Enum):
    """
    Enumeration for backtest evaluation focus areas.

    The available metrics are:
        - backtest_start_date
        - backtest_end_date
        - equity_curve
        - final_value
        - total_growth
        - total_growth_percentage
        - total_net_gain
        - total_net_gain_percentage
        - total_loss
        - total_loss_percentage
        - cumulative_return
        - cumulative_return_series
        - cagr
        - sharpe_ratio
        - rolling_sharpe_ratio
        - sortino_ratio
        - calmar_ratio
        - profit_factor
        - annual_volatility
        - monthly_returns
        - yearly_returns
        - drawdown_series
        - max_drawdown
        - max_drawdown_absolute
        - max_daily_drawdown
        - max_drawdown_duration
        - trades_per_year
        - trade_per_day
        - exposure_ratio
        - cumulative_exposure
        - best_trade
        - worst_trade
        - number_of_positive_trades
        - percentage_positive_trades
        - number_of_negative_trades
        - percentage_negative_trades
        - average_trade_duration
        - average_trade_size
        - average_trade_loss
        - average_trade_loss_percentage
        - average_trade_gain
        - average_trade_gain_percentage
        - average_trade_return
        - average_trade_return_percentage
        - median_trade_return
        - number_of_trades
        - number_of_trades_closed
        - number_of_trades_opened
        - number_of_trades_open_at_end
        - win_rate
        - current_win_rate
        - win_loss_ratio
        - current_win_loss_ratio
        - percentage_winning_months
        - percentage_winning_years
        - average_monthly_return
        - average_monthly_return_losing_months
        - average_monthly_return_winning_months
        - best_month
        - best_year
        - worst_month
        - worst_year
        - total_number_of_days
        - current_average_trade_gain
        - current_average_trade_return
        - current_average_trade_duration
        - current_average_trade_loss
    """
    BALANCED = "balanced"
    PROFIT = "profit"
    FREQUENCY = "frequency"
    RISK_ADJUSTED = "risk_adjusted"

    @staticmethod
    def from_string(value: str):

        if isinstance(value, str):

            for entry in BacktestEvaluationFocus:

                if value.upper() == entry.value:
                    return entry

            raise ValueError(
                f"Could not convert {value} to BacktestEvaluationFocus"
            )
        return None

    @staticmethod
    def from_value(value):

        if isinstance(value, str):
            return BacktestEvaluationFocus.from_string(value)

        if isinstance(value, BacktestEvaluationFocus):

            for entry in BacktestEvaluationFocus:

                if value == entry:
                    return entry

        raise ValueError(
            f"Could not convert {value} to BacktestEvaluationFocus"
        )

    def equals(self, other):

        if isinstance(other, Enum):
            return self.value == other.value
        else:
            return BacktestEvaluationFocus.from_string(other) == self

    def get_weights(self):
        """
        Get evaluation weights for different focus areas.
        Returns a dictionary with metric weights where:
        - Positive weights favor higher values
        - Negative weights favor lower values (penalties)
        - Zero weights ignore the metric
        """

        if self == BacktestEvaluationFocus.BALANCED:
            return {
                # Core profitability metrics (moderate weight)
                "total_net_gain_percentage": 2.0,
                "cagr": 1.5,
                "average_trade_return_percentage": 1.0,

                # Risk-adjusted returns (important for balance)
                "sharpe_ratio": 2.0,
                "sortino_ratio": 1.5,
                "calmar_ratio": 1.0,
                "profit_factor": 1.5,

                # Risk management (penalties for bad metrics)
                "max_drawdown": -1.5,
                "max_drawdown_duration": -0.5,
                "annual_volatility": -0.8,

                # Trading consistency
                "win_rate": 1.5,
                "win_loss_ratio": 1.0,
                "number_of_trades": 0.8,  # Some activity needed

                # Efficiency metrics
                "exposure_ratio": 0.5,
                "trades_per_year": 0.3,
            }

        elif self == BacktestEvaluationFocus.PROFIT:
            return {
                # Maximize absolute and relative profits
                "total_net_gain_percentage": 3.0,
                "cagr": 2.5,
                "total_net_gain": 2.0,
                "average_trade_return_percentage": 1.5,
                "average_trade_gain_percentage": 1.0,

                # Profit consistency
                "win_rate": 2.0,
                "profit_factor": 2.0,
                "percentage_positive_trades": 1.0,

                # Risk secondary (but still important)
                "sharpe_ratio": 1.0,
                "max_drawdown": -1.0,

                # Activity level (need some trades)
                "number_of_trades": 0.5,

                # Monthly/yearly consistency
                "percentage_winning_months": 0.8,
                "average_monthly_return": 1.0,
            }

        elif self == BacktestEvaluationFocus.FREQUENCY:
            return {
                # High trading activity with good results
                "number_of_trades": 3.0,
                "trades_per_year": 2.5,
                "exposure_ratio": 2.0,

                # Profitability per trade (scaled for frequency)
                "average_trade_return_percentage": 2.0,
                "win_rate": 2.5,
                "total_net_gain_percentage": 1.5,

                # Consistency across many trades
                "win_loss_ratio": 1.5,
                "percentage_positive_trades": 1.0,

                # Risk management for frequent trading
                "max_drawdown": -1.5,
                "sharpe_ratio": 1.0,
                "profit_factor": 1.2,

                # Duration efficiency
                "average_trade_duration": -0.3,  # Prefer shorter trades
            }

        elif self == BacktestEvaluationFocus.RISK_ADJUSTED:
            return {
                # Risk-adjusted performance metrics (highest priority)
                "sharpe_ratio": 3.0,
                "sortino_ratio": 2.5,
                "calmar_ratio": 2.0,

                # Risk management (strong penalties)
                "max_drawdown": -3.0,
                "max_drawdown_duration": -1.5,
                "annual_volatility": -2.0,

                # Consistent performance
                "win_rate": 2.0,
                "win_loss_ratio": 1.5,
                "percentage_winning_months": 1.5,

                # Stable returns
                "average_trade_return_percentage": 1.5,
                "total_net_gain_percentage": 1.0,
                "profit_factor": 1.8,

                # Reasonable activity
                "number_of_trades": 0.5,

                # Downside protection
                "average_trade_loss_percentage": -1.0,
                "percentage_negative_trades": -1.0,
            }

        # Fallback to balanced if unknown focus
        return self.get_weights() \
            if self != BacktestEvaluationFocus.BALANCED else {}
