"""TimeRule — composable per-day execution times.

A ``TimeRule`` produces zero or more ``datetime.time`` values within a
calendar day. Combined with a ``DateRule`` inside a ``Schedule``, this
determines when the strategy fires.

Market-relative rules (``market_open``, ``market_close``,
``every_minute``) require a ``TradingCalendar`` (issue #444). Until
that lands, calling them without an explicit calendar raises
``NotImplementedError`` with an actionable message pointing at
``TimeRule.at(...)`` for clock-time scheduling.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .trading_calendar import TradingCalendar


_CALENDAR_REQUIRED_HINT = (
    "Market-relative TimeRules require a TradingCalendar (issue #444). "
    "Until calendar integration ships, use TimeRule.at(hour, minute) for "
    "absolute clock-time scheduling, or compose with Schedule.every(...) "
    "for interval-based scheduling."
)


class TimeRule(ABC):
    """Abstract base class for intra-day time-of-day scheduling rules."""

    @abstractmethod
    def times_for(
        self,
        day: date,
        calendar: Optional["TradingCalendar"] = None,
    ) -> List[time]:
        """Return the execution ``time``s within ``day`` under this rule."""

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @staticmethod
    def at(hour: int, minute: int = 0, second: int = 0) -> "TimeRule":
        """Fire once per day at the given absolute clock time (UTC)."""
        return _At(hour=hour, minute=minute, second=second)

    @staticmethod
    def market_open(minutes: int = 0) -> "TimeRule":
        """Fire ``minutes`` after market open. Requires a TradingCalendar."""
        if minutes < 0:
            raise ValueError(
                "market_open(minutes=...) must be >= 0; for pre-open use "
                "TimeRule.at(...) directly."
            )
        return _MarketRelative(open_anchor=True, minutes=minutes)

    @staticmethod
    def market_close(minutes: int = 0) -> "TimeRule":
        """Fire ``minutes`` before market close. Requires a TradingCalendar."""
        if minutes < 0:
            raise ValueError(
                "market_close(minutes=...) must be >= 0; for post-close use "
                "TimeRule.at(...) directly."
            )
        return _MarketRelative(open_anchor=False, minutes=minutes)

    @staticmethod
    def every_minute() -> "TimeRule":
        """Fire every minute of the trading session. Requires a calendar."""
        return _EveryMinute()


# ----------------------------------------------------------------------
# Implementations
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _At(TimeRule):
    hour: int
    minute: int = 0
    second: int = 0

    def __post_init__(self):
        if not 0 <= self.hour < 24:
            raise ValueError(
                f"hour must be in [0, 24); got {self.hour}"
            )
        if not 0 <= self.minute < 60:
            raise ValueError(
                f"minute must be in [0, 60); got {self.minute}"
            )
        if not 0 <= self.second < 60:
            raise ValueError(
                f"second must be in [0, 60); got {self.second}"
            )

    def times_for(self, day, calendar=None):
        return [time(self.hour, self.minute, self.second)]


@dataclass(frozen=True)
class _MarketRelative(TimeRule):
    open_anchor: bool
    minutes: int = 0

    def times_for(self, day, calendar=None):
        if calendar is None:
            raise NotImplementedError(_CALENDAR_REQUIRED_HINT)
        session = calendar.session_for(day)
        if session is None:
            return []
        anchor = session.open if self.open_anchor else session.close
        delta = timedelta(
            minutes=self.minutes if self.open_anchor else -self.minutes
        )
        target = (datetime.combine(day, anchor) + delta).time()
        return [target]


@dataclass(frozen=True)
class _EveryMinute(TimeRule):
    def times_for(self, day, calendar=None):
        if calendar is None:
            raise NotImplementedError(_CALENDAR_REQUIRED_HINT)
        session = calendar.session_for(day)
        if session is None:
            return []
        result = []
        cur = datetime.combine(day, session.open)
        end = datetime.combine(day, session.close)
        while cur <= end:
            result.append(cur.time())
            cur += timedelta(minutes=1)
        return result
