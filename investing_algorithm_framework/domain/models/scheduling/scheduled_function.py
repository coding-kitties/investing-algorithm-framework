"""ScheduledFunction — bind a Schedule to a named method on a strategy.

A ``TradingStrategy`` may declare a list of ``ScheduledFunction``s
alongside its primary ``schedule``. The scheduler invokes the named
method whenever that function's ``Schedule`` fires, independent of the
strategy's default ``run_strategy`` schedule.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .date_rule import DateRule
from .schedule import Schedule
from .time_rule import TimeRule


@dataclass(frozen=True)
class ScheduledFunction:
    """Binds a Schedule to a method by name.

    Two construction forms are supported:

    * Explicit::

        ScheduledFunction(func="rebalance", schedule=Schedule.on(...))

    * Shorthand — builds the Schedule for you::

        ScheduledFunction(
            func="rebalance",
            date_rule=DateRule.month_start(),
            time_rule=TimeRule.market_open(minutes=30),
        )

    The two forms are mutually exclusive.
    """

    func: str
    schedule: Optional[Schedule] = None
    date_rule: Optional[DateRule] = None
    time_rule: Optional[TimeRule] = None

    def __post_init__(self):
        if not isinstance(self.func, str) or not self.func:
            raise ValueError(
                "ScheduledFunction.func must be a non-empty method name "
                f"(got {self.func!r})."
            )

        has_explicit = self.schedule is not None
        has_shorthand = (
            self.date_rule is not None or self.time_rule is not None
        )

        if has_explicit and has_shorthand:
            raise ValueError(
                "ScheduledFunction: pass either ``schedule=`` OR "
                "``date_rule=``/``time_rule=``, not both."
            )

        if not has_explicit:
            if self.date_rule is None or self.time_rule is None:
                raise ValueError(
                    "ScheduledFunction requires either ``schedule=`` or "
                    "BOTH ``date_rule=`` and ``time_rule=``."
                )
            object.__setattr__(
                self,
                "schedule",
                Schedule.on(self.date_rule, self.time_rule),
            )
