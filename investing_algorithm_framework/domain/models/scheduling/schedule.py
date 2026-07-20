"""Schedule — the v9.0 replacement for ``time_unit`` + ``interval``.

A ``Schedule`` is either *interval-based* (run every N time-units) or
*rule-based* (run when a ``DateRule`` AND a ``TimeRule`` match against
a trading calendar). The two modes are mutually exclusive — construct
via the ``Schedule.every(...)`` or ``Schedule.on(...)`` factories.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Iterator, Optional

from ..time_unit import TimeUnit
from .date_rule import DateRule
from .time_rule import TimeRule

if TYPE_CHECKING:  # pragma: no cover
    from .trading_calendar import TradingCalendar


@dataclass(frozen=True)
class Schedule:
    """Strategy execution schedule.

    Construct in one of two ways:

    * ``Schedule.every(interval, time_unit)`` — fire every
      ``interval`` ``time_unit``s. Equivalent to the legacy
      ``time_unit``/``interval`` pair on ``TradingStrategy``.
    * ``Schedule.on(date_rule, time_rule)`` — fire whenever
      ``date_rule`` matches the day AND ``time_rule`` yields a time.

    Schedules are immutable and hashable; instances may be shared
    across strategies safely.
    """

    time_unit: Optional[TimeUnit] = None
    interval: Optional[int] = None
    date_rule: Optional[DateRule] = None
    time_rule: Optional[TimeRule] = None

    def __post_init__(self):
        interval_mode = (
            self.time_unit is not None and self.interval is not None
        )
        rule_mode = (
            self.date_rule is not None and self.time_rule is not None
        )
        if interval_mode == rule_mode:
            raise ValueError(
                "Schedule must be defined either by (time_unit, interval) "
                "OR by (date_rule, time_rule). Use Schedule.every(...) or "
                "Schedule.on(...)."
            )
        if interval_mode:
            if not isinstance(self.interval, int) or self.interval <= 0:
                raise ValueError(
                    f"interval must be a positive int; got {self.interval!r}"
                )
            object.__setattr__(
                self, "time_unit", TimeUnit.from_value(self.time_unit)
            )

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @staticmethod
    def every(interval: int, time_unit: TimeUnit) -> "Schedule":
        """Interval-mode schedule: fire every ``interval`` ``time_unit``s."""
        return Schedule(time_unit=time_unit, interval=interval)

    @staticmethod
    def on(date_rule: DateRule, time_rule: TimeRule) -> "Schedule":
        """Rule-mode schedule: fire when both rules match."""
        return Schedule(date_rule=date_rule, time_rule=time_rule)

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------

    @property
    def is_interval(self) -> bool:
        return self.time_unit is not None

    @property
    def is_rule_based(self) -> bool:
        return self.date_rule is not None

    def step(self) -> Optional[timedelta]:
        """Return the step ``timedelta`` for interval mode, else ``None``."""
        if not self.is_interval:
            return None
        unit = self.time_unit
        if TimeUnit.SECOND.equals(unit):
            return timedelta(seconds=self.interval)
        if TimeUnit.MINUTE.equals(unit):
            return timedelta(minutes=self.interval)
        if TimeUnit.HOUR.equals(unit):
            return timedelta(hours=self.interval)
        if TimeUnit.DAY.equals(unit):
            return timedelta(days=self.interval)
        raise ValueError(f"Unsupported time unit: {unit}")

    # ------------------------------------------------------------------
    # Firing semantics
    # ------------------------------------------------------------------

    def iter_run_times(
        self,
        start: datetime,
        end: datetime,
        calendar: Optional["TradingCalendar"] = None,
    ) -> Iterator[datetime]:
        """Yield every datetime in ``[start, end]`` at which the schedule
        fires.

        Interval mode ignores ``calendar``. Rule mode uses it to filter
        trading days and to compute market-relative times.
        """
        if self.is_interval:
            step = self.step()
            cur = start
            while cur <= end:
                yield cur
                cur += step
            return

        tz = start.tzinfo
        day = start.date()
        while day <= end.date():
            if self.date_rule.matches(day, calendar):
                for tod in self.time_rule.times_for(day, calendar):
                    moment = datetime.combine(day, tod, tzinfo=tz)
                    if start <= moment <= end:
                        yield moment
            day += timedelta(days=1)

    def is_due(
        self,
        now: datetime,
        last_run: Optional[datetime],
        calendar: Optional["TradingCalendar"] = None,
    ) -> bool:
        """Return ``True`` if the schedule should fire at ``now``.

        * Interval mode: ``last_run is None`` or ``now >= last_run + step()``.
        * Rule mode: ``date_rule`` matches today and there is a rule-time
          at-or-before ``now`` that has not yet been served.
        """
        if self.is_interval:
            if last_run is None:
                return True
            return now >= last_run + self.step()

        if not self.date_rule.matches(now.date(), calendar):
            return False
        for tod in self.time_rule.times_for(now.date(), calendar):
            moment = datetime.combine(now.date(), tod, tzinfo=now.tzinfo)
            if moment > now:
                continue
            if last_run is None or moment > last_run:
                return True
        return False
