"""Value objects describing portfolio reconciliation outcomes and scheduled
external cash flows used by ``Context.sync_portfolio``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class SyncResult:
    """Outcome of a single :meth:`Context.sync_portfolio` call.

    Attributes:
        market: Market the sync was performed on.
        kind: One of ``"noop"``, ``"deposit"``, ``"withdrawal"``.
        delta: ``broker_available - previous_unallocated``.
            Positive = deposit detected, negative = shortfall absorbed.
        broker_available: Trading-symbol balance the broker reports
            (in backtest: ``previous_unallocated`` plus pending simulated
            deposits since the last sync; in live: free balance minus
            cash reserved for not-yet-acknowledged orders).
        previous_unallocated: Local unallocated balance *before* the sync.
        new_unallocated: Local unallocated balance *after* the sync.
        within_tolerance: ``True`` when ``abs(delta)`` is below the
            configured tolerance and the sync was therefore treated as a
            noop.
        reserved_for_pending_orders: Cash subtracted from the raw broker
            balance to account for orders the framework knows about but
            the exchange has not yet filled or cancelled. Always ``0`` in
            backtest mode.
    """

    market: str
    kind: str
    delta: float
    broker_available: float
    previous_unallocated: float
    new_unallocated: float
    within_tolerance: bool = False
    reserved_for_pending_orders: float = 0.0


@dataclass(frozen=True)
class ScheduledDeposit:
    """A simulated external cash flow applied to a backtested portfolio.

    Use one of two scheduling modes:

    * **Recurring** — set ``time_unit`` and ``interval`` (e.g. monthly
      paycheck). The deposit fires every ``interval`` units of
      ``time_unit`` starting from the backtest start date.
    * **One-shot** — set ``on`` to a specific ``datetime``. The deposit
      fires once at that timestamp.

    Attributes:
        amount: Amount to credit to ``unallocated``. Negative values are
            treated as withdrawals (drawing down the simulated broker
            balance).
        time_unit: Recurring cadence unit (DAY, HOUR, …). Mutually
            exclusive with ``on``.
        interval: Recurring cadence count (e.g. ``30`` with
            ``TimeUnit.DAY`` = every 30 days). Mutually exclusive
            with ``on``.
        on: Wall-clock timestamp for a one-shot deposit. Mutually
            exclusive with ``time_unit``/``interval``.
    """

    amount: float
    time_unit: Optional[object] = None  # TimeUnit; typed loosely to avoid cycle
    interval: Optional[int] = None
    on: Optional[datetime] = None
    fire_on_anchor: bool = False
    """If ``True`` for a recurring deposit, the first firing happens at the
    anchor moment (typically the backtest start) instead of at
    ``anchor + interval``. Useful for "deposit immediately at start, then
    every N days"."""

    def __post_init__(self) -> None:
        recurring = self.time_unit is not None or self.interval is not None
        if recurring and self.on is not None:
            raise ValueError(
                "ScheduledDeposit: pass either (time_unit, interval) for a "
                "recurring deposit or 'on' for a one-shot deposit, not both."
            )
        if not recurring and self.on is None:
            raise ValueError(
                "ScheduledDeposit: must specify either (time_unit, interval) "
                "or 'on'."
            )
        if recurring and (self.time_unit is None or self.interval is None):
            raise ValueError(
                "ScheduledDeposit: recurring deposits require both "
                "time_unit and interval."
            )
        if recurring and self.interval <= 0:
            raise ValueError(
                "ScheduledDeposit: interval must be positive."
            )
        if self.on is not None and self.on.tzinfo is None:
            raise ValueError(
                "ScheduledDeposit: 'on' must be timezone-aware. Use "
                "datetime(..., tzinfo=timezone.utc) or similar."
            )
        if self.fire_on_anchor and not recurring:
            raise ValueError(
                "ScheduledDeposit: fire_on_anchor only applies to recurring "
                "deposits."
            )
