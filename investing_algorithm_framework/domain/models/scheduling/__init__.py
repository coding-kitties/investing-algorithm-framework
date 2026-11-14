"""Scheduling primitives (issue #441).

This module provides composable ``DateRule`` and ``TimeRule`` types that
combine into a ``Schedule`` — the v9.0 replacement for the legacy
``time_unit`` + ``interval`` pair on ``TradingStrategy``. A
``ScheduledFunction`` binds a ``Schedule`` to a named method on a
strategy, enabling multiple, independently scheduled functions per
strategy.

Market-relative rules (``TimeRule.market_open``, ``market_close``,
``every_minute``) require a ``TradingCalendar`` (issue #444). Until the
calendar layer ships, calling them without an explicit calendar raises
``NotImplementedError`` with an actionable message.
"""
from .date_rule import DateRule
from .schedule import Schedule
from .scheduled_function import ScheduledFunction
from .time_rule import TimeRule

__all__ = [
    "DateRule",
    "Schedule",
    "ScheduledFunction",
    "TimeRule",
]
