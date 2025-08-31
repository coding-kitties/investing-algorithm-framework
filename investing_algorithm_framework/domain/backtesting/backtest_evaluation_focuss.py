from enum import Enum


default_weights = {
    # Profitability
    "total_net_gain": 3.0,
    "gross_loss": 0.0,
    "growth": 0.0,
    "trades_average_return": 0.0,

    # Risk-adjusted returns
    "sharpe_ratio": 1.0,
    "sortino_ratio": 1.0,
    "profit_factor": 1.0,

    # Risk
    "max_drawdown": -2.0,
    "max_drawdown_duration": -0.5,

    # Trading activity
    "number_of_trades": 2.0,
    "win_rate": 3.0,

    # Exposure
    "cumulative_exposure": 0.5,
    "exposure_ratio": 0.0,
}


class BacktestEvaluationFocus(Enum):
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
        # default / balanced
        base = {
            "total_net_gain": 3.0,
            "win_rate": 3.0,
            "number_of_trades": 2.0,
            "sharpe_ratio": 1.0,
            "sortino_ratio": 1.0,
            "profit_factor": 1.0,
            "max_drawdown": -2.0,
            "max_drawdown_duration": -0.5,
            "total_net_loss": 0.0,
            "total_return": 0.0,
            "avg_return_per_trade": 0.0,
            "exposure_factor": 0.5,
            "exposure_ratio": 0.0,
            "exposure_time": 0.0,
        }

        if self != BacktestEvaluationFocus.BALANCED:

            # apply presets
            if self == BacktestEvaluationFocus.PROFIT:
                base.update({
                    "total_net_gain": 3.0,
                    "win_rate": 2.0,
                    "number_of_trades": 1.0,
                })
            elif self == BacktestEvaluationFocus.FREQUENCY:
                base.update({
                    "number_of_trades": 3.0,
                    "win_rate": 2.0,
                    "total_net_gain": 2.0,
                })
            elif self == BacktestEvaluationFocus.RISK_ADJUSTED:
                base.update({
                    "sharpe_ratio": 3.0,
                    "sortino_ratio": 3.0,
                    "max_drawdown": -3.0,
                })

        return base
