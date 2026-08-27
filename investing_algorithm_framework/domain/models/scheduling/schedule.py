"""Schedule — the v9.0 replacement for ``time_unit`` + ``interval``.

A ``Schedule`` is either *interval-based* (run every N time-units) or
*rule-based* (run when a ``DateRule`` AND a ``TimeRule`` match against
a trading calendar). The two modes are mutually exclusive — construct
via the ``Schedule.every(...)`` or ``Schedule.on(...)`` factories.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Iterator, Optional

from ..time_unit import TimeUnit
from .date_rule import DateRule
from .time_rule import TimeRule

if TYPE_CHECKING:  # pragma: no cover
    from .trading_calendar import TradingCalendar

# Default alignment reference for interval-mode schedules: with no
# explicit ``anchor``, slots fall on whole-unit UTC boundaries (e.g.
# every 2 hours -> 00:00, 02:00, 04:00, ... 08:00, 10:00, 12:00, ...)
# instead of drifting relative to whenever the schedule happened to
# start or last run.
_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


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
    anchor: Optional[datetime] = None

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
    def every(
        interval: int,
        time_unit: TimeUnit,
        anchor: Optional[datetime] = None,
    ) -> "Schedule":
        """Interval-mode schedule: fire every ``interval`` ``time_unit``s.

        ``anchor`` is an optional reference datetime that the fire
        times align to (only its offset modulo the step matters, not
        the specific date) — e.g. an anchor of ``09:30`` with a 2 hour
        step fires at 09:30, 11:30, 13:30, ... every day. Defaults to
        the UNIX epoch (UTC midnight), so schedules align to whole
        UTC clock boundaries (every 2 hours -> 00:00, 02:00, 04:00,
        ..., 08:00, 10:00, 12:00, ...) instead of drifting relative to
        whenever the app happened to start or last run.
        """
        return Schedule(
            time_unit=time_unit, interval=interval, anchor=anchor
        )

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

    def _slot_start(self, moment: datetime) -> datetime:
        """Return the start of the anchor-aligned interval slot that
        ``moment`` falls into (interval mode only).

        Slots are fixed points on the wall clock derived from
        ``anchor`` (default: the UNIX epoch) and ``step()`` — they do
        not depend on ``last_run``, so recording a run at an arbitrary
        time (e.g. a manually triggered/forced run) never shifts the
        schedule's natural cadence: the next slot boundary stays the
        same regardless of when the previous run actually happened.
        """
        step = self.step()
        anchor = self.anchor if self.anchor is not None else _EPOCH
        slot_index = (moment - anchor) // step
        return anchor + slot_index * step

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

        Interval mode ignores ``calendar`` and aligns to anchor slots
        (see :meth:`_slot_start`) rather than starting exactly at
        ``start``, so backtest and live cadences agree. Rule mode uses
        ``calendar`` to filter trading days and to compute
        market-relative times.
        """
        if self.is_interval:
            step = self.step()
            cur = self._slot_start(start)
            if cur < start:
                cur += step
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

        * Interval mode: ``last_run is None`` or ``last_run`` falls
          before the start of ``now``'s anchor-aligned slot (see
          :meth:`_slot_start`). A run recorded partway through a slot
          (e.g. a manual/forced run) still only counts for that slot —
          the next natural slot remains due at its fixed boundary.
        * Rule mode: ``date_rule`` matches today and there is a rule-time
          at-or-before ``now`` that has not yet been served.
        """
        if self.is_interval:
            if last_run is None:
                return True
            return last_run < self._slot_start(now)

        if not self.date_rule.matches(now.date(), calendar):
            return False
        for tod in self.time_rule.times_for(now.date(), calendar):
            moment = datetime.combine(now.date(), tod, tzinfo=now.tzinfo)
            if moment > now:
                continue
            if last_run is None or moment > last_run:
                return True
        return False

    def next_run_after(
        self,
        after: datetime,
        calendar: Optional["TradingCalendar"] = None,
    ) -> Optional[datetime]:
        """Return the next datetime, strictly after ``after``, at which
        this schedule fires.

        * Interval mode: the start of the anchor-aligned slot after
          ``after``'s slot (see :meth:`_slot_start`) — always a fixed
          grid point, independent of what ``after`` actually is.
        * Rule mode: scans forward day-by-day (bounded to one year) for
          the earliest rule-time later than ``after``; returns ``None``
          if none is found within that window.
        """
        if self.is_interval:
            return self._slot_start(after) + self.step()

        day = after.date()
        for _ in range(366):
            if self.date_rule.matches(day, calendar):
                for tod in sorted(self.time_rule.times_for(day, calendar)):
                    moment = datetime.combine(day, tod, tzinfo=after.tzinfo)
                    if moment > after:
                        return moment
            day += timedelta(days=1)
        return None
