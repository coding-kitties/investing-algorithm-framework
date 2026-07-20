"""DateRule — composable per-day predicates for strategy scheduling.

A ``DateRule`` decides whether a given calendar day is an *execution
day* for the strategy. A rule alone does not produce datetimes; pair
it with a ``TimeRule`` inside a ``Schedule`` to get firing times.

Rules that need to know which days the venue is open accept an
optional ``calendar`` argument (a ``TradingCalendar``, issue #444).
When omitted, every calendar day is treated as a trading day; this is
appropriate for 24/7 venues like crypto exchanges.
"""
from __future__ import annotations

import calendar as _stdcal
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import date, timedelta
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # pragma: no cover
    from .trading_calendar import TradingCalendar


class DateRule(ABC):
    """Abstract base class for date-level scheduling rules."""

    @abstractmethod
    def matches(
        self,
        day: date,
        calendar: Optional["TradingCalendar"] = None,
    ) -> bool:
        """Return ``True`` if ``day`` is an execution day under this rule."""

    # ------------------------------------------------------------------
    # Factories
    # ------------------------------------------------------------------

    @staticmethod
    def every_day() -> "DateRule":
        """Match every (trading) day."""
        return _EveryDay()

    @staticmethod
    def week_start(days_offset: int = 0) -> "DateRule":
        """Match the first trading day of each ISO week, plus ``days_offset``.

        Without a calendar this is Monday + ``days_offset``.
        """
        if days_offset < 0:
            raise ValueError("days_offset must be >= 0 for week_start")
        return _WeekAnchor(anchor_start=True, days_offset=days_offset)

    @staticmethod
    def week_end(days_offset: int = 0) -> "DateRule":
        """Match the last trading day of each ISO week, minus ``days_offset``.

        Without a calendar this is Sunday - ``days_offset``.
        """
        if days_offset < 0:
            raise ValueError("days_offset must be >= 0 for week_end")
        return _WeekAnchor(anchor_start=False, days_offset=days_offset)

    @staticmethod
    def month_start(days_offset: int = 0) -> "DateRule":
        """Match the first trading day of each month, plus ``days_offset``."""
        if days_offset < 0:
            raise ValueError("days_offset must be >= 0 for month_start")
        return _MonthAnchor(anchor_start=True, days_offset=days_offset)

    @staticmethod
    def month_end(days_offset: int = 0) -> "DateRule":
        """Match the last trading day of each month, minus ``days_offset``."""
        if days_offset < 0:
            raise ValueError("days_offset must be >= 0 for month_end")
        return _MonthAnchor(anchor_start=False, days_offset=days_offset)


# ----------------------------------------------------------------------
# Implementations
# ----------------------------------------------------------------------


@dataclass(frozen=True)
class _EveryDay(DateRule):
    def matches(self, day, calendar=None):
        if calendar is None:
            return True
        return calendar.is_trading_day(day)


@dataclass(frozen=True)
class _WeekAnchor(DateRule):
    anchor_start: bool
    days_offset: int = 0

    def matches(self, day, calendar=None):
        if calendar is None:
            # ISO week: Monday=0..Sunday=6.
            week_monday = day - timedelta(days=day.weekday())
            week_sunday = week_monday + timedelta(days=6)
            if self.anchor_start:
                return day == week_monday + timedelta(days=self.days_offset)
            return day == week_sunday - timedelta(days=self.days_offset)

        sessions = calendar.trading_sessions_in_week(day)
        if not sessions:
            return False
        if self.anchor_start:
            target = self.days_offset
        else:
            target = len(sessions) - 1 - self.days_offset
        if not 0 <= target < len(sessions):
            return False
        return day == sessions[target]


@dataclass(frozen=True)
class _MonthAnchor(DateRule):
    anchor_start: bool
    days_offset: int = 0

    def matches(self, day, calendar=None):
        if calendar is None:
            first = day.replace(day=1)
            last_dom = _stdcal.monthrange(day.year, day.month)[1]
            last = day.replace(day=last_dom)
            if self.anchor_start:
                return day == first + timedelta(days=self.days_offset)
            return day == last - timedelta(days=self.days_offset)

        sessions = calendar.trading_sessions_in_month(day)
        if not sessions:
            return False
        if self.anchor_start:
            target = self.days_offset
        else:
            target = len(sessions) - 1 - self.days_offset
        if not 0 <= target < len(sessions):
            return False
        return day == sessions[target]
