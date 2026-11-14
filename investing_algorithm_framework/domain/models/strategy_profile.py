from dataclasses import dataclass, field
from typing import List, Optional

from .scheduling import Schedule, ScheduledFunction
from .time_unit import TimeUnit


@dataclass(frozen=True)
class StrategyProfile:
    """
    StrategyProfile class that represents the profile of a trading strategy.

    v9.0 breaking change: ``interval`` and ``time_unit`` were replaced by a
    single :class:`Schedule` instance. Use ``profile.schedule.time_unit``
    and ``profile.schedule.interval`` when the schedule is interval-mode,
    or iterate fire-times via ``profile.schedule.iter_run_times(start, end)``
    for rule-based schedules.
    """
    strategy_id: str = None
    schedule: Optional[Schedule] = None
    scheduled_functions: List[ScheduledFunction] = field(default_factory=list)
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
        """Approximate number of runs per day for an interval-mode schedule.

        Returns 0 for rule-based schedules (where the number of runs per
        day is calendar-dependent and not knowable without a date range).
        """
        if self.schedule is None or not self.schedule.is_interval:
            return 0
        interval = self.schedule.interval
        time_unit = self.schedule.time_unit
        if TimeUnit.SECOND.equals(time_unit):
            return 86400 / interval
        if TimeUnit.MINUTE.equals(time_unit):
            return 1440 / interval
        if TimeUnit.HOUR.equals(time_unit):
            return 24 / interval
        if TimeUnit.DAY.equals(time_unit):
            return 1 / interval
        return 0
