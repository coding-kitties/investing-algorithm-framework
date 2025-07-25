from dataclasses import dataclass

from .time_unit import TimeUnit


@dataclass(frozen=True)
class StrategyProfile:
    """
    StrategyProfile class that represents the profile of a trading strategy.
    """
    strategy_id: str = None
    interval: int = None
    time_unit: TimeUnit = None
    trading_time_frame: str = None
    trading_time_frame_start_date: str = None
    backtest_start_date_data: str = None
    backtest_data_index_date: str = None
    symbols: list = None
    market: str = None
    trading_data_type: str = None
    trading_data_types: list = None
    data_sources: list = None

    def get_runs_per_day(self):

        if self.time_unit is None:
            return 0
        elif TimeUnit.SECOND.equals(self.time_unit):
            return 86400 / self.interval
        elif TimeUnit.MINUTE.equals(self.time_unit):
            return 1440 / self.interval
        else:
            return 24 / self.interval
