"""Broker balance tracker — public reconciliation surface for ``Context``.

This service is the *single source of truth* for "how much cash does the
broker actually have for me?" and is used by :meth:`Context.sync_portfolio`.

Design
------

The tracker is intentionally tiny and engine-agnostic:

* In **live mode** the framework does not populate the tracker; callers
  query a registered :class:`PortfolioProvider` directly. The tracker only
  exposes the configuration knobs (``auto_sync`` flag) for the live
  runtime to consult.
* In **backtest mode** there is no broker, so the engine simulates one.
  The event-loop and vector-backtest engines call
  :meth:`fire_due_deposits` at every tick to convert any
  :class:`ScheduledDeposit` whose cadence has elapsed into "pending"
  external balance. ``Context.sync_portfolio`` then drains that pending
  balance into the local portfolio's ``unallocated`` field — *exactly* the
  same code path a strategy would hit in live mode when a paycheck lands
  on the exchange.

The result is a symmetric contract: the same ``context.sync_portfolio()``
call inside a strategy works unchanged across event-backtest, vector-backtest
(via the per-bar deposit application) and live trading.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from investing_algorithm_framework.domain import (
    OperationalException,
    ScheduledDeposit,
    TimeUnit,
)

logger = logging.getLogger(__name__)


def _interval_delta(time_unit: TimeUnit, interval: int) -> timedelta:
    if time_unit == TimeUnit.SECOND:
        return timedelta(seconds=interval)
    if time_unit == TimeUnit.MINUTE:
        return timedelta(minutes=interval)
    if time_unit == TimeUnit.HOUR:
        return timedelta(hours=interval)
    if time_unit == TimeUnit.DAY:
        return timedelta(days=interval)
    if time_unit == TimeUnit.WEEK:
        return timedelta(weeks=interval)
    if time_unit == TimeUnit.MONTH:
        # Calendar months are not a fixed timedelta; approximate as 30 days.
        # ScheduledDeposit cadence is intentionally coarse — users who need
        # exact calendar months should pass one-shot ``on=`` deposits.
        logger.warning(
            "ScheduledDeposit with TimeUnit.MONTH is approximated as "
            "30 days/month (~12.17 firings/year). For exact calendar "
            "months, use one-shot ScheduledDeposit(on=...) entries."
        )
        return timedelta(days=30 * interval)
    raise OperationalException(
        f"Unsupported TimeUnit for ScheduledDeposit: {time_unit}"
    )


_AUTO_SYNC_ERROR_MODES = ("raise", "warn", "halt")


@dataclass
class _MarketState:
    schedule: List[ScheduledDeposit] = field(default_factory=list)
    auto_sync: bool = False
    auto_sync_error_mode: str = "raise"
    pending: float = 0.0
    # Net cash flow absorbed by sync_portfolio since the last snapshot
    # drain. Used by the snapshot service to populate ``cash_flow`` so
    # TWR-style metrics can subtract external deposits / withdrawals.
    cash_flow_since_snapshot: float = 0.0
    # Lifetime sum of absorbed cash flow (deposits − withdrawals).
    total_cash_flow: float = 0.0
    # last-fired timestamp per recurring deposit index
    last_fired: Dict[int, datetime] = field(default_factory=dict)
    # set of one-shot deposit indices that already fired
    one_shot_fired: set = field(default_factory=set)
    # set of recurring deposit indices that have fired their anchor-day
    # firing (only relevant when ScheduledDeposit.fire_on_anchor=True).
    anchor_fired: set = field(default_factory=set)


class BrokerBalanceTracker:
    """In-memory store of deposit schedules and pending external balance.

    A single instance lives on the :class:`App` (and is injected into
    :class:`Context` via the dependency container). Keys are the **uppercased
    market identifier** (matching :class:`PortfolioConfiguration.market`).
    Lookups are case-insensitive — ``"binance"`` and ``"BINANCE"`` resolve
    to the same state.
    """

    def __init__(self) -> None:
        self._markets: Dict[str, _MarketState] = {}

    @staticmethod
    def _key(market: str) -> str:
        if market is None:
            raise OperationalException(
                "BrokerBalanceTracker: market identifier cannot be None."
            )
        return str(market).upper()

    def _get(self, market: str) -> _MarketState:
        key = self._key(market)
        if key not in self._markets:
            self._markets[key] = _MarketState()
        return self._markets[key]

    def has_market(self, market: str) -> bool:
        return self._key(market) in self._markets

    def set_schedule(
        self, market: str, schedule: List[ScheduledDeposit]
    ) -> None:
        """Replace the deposit schedule for a market.

        ``pending`` and ``cash_flow_since_snapshot`` are preserved (they
        represent already-credited cash, not part of the schedule itself).
        Per-deposit firing history is cleared so the new schedule is
        evaluated from scratch on the next ``fire_due_deposits`` call.
        """
        if schedule is None:
            schedule = []
        for entry in schedule:
            if not isinstance(entry, ScheduledDeposit):
                raise OperationalException(
                    "BrokerBalanceTracker.set_schedule: every entry must be "
                    f"a ScheduledDeposit, got {type(entry).__name__}."
                )
        state = self._get(market)
        state.schedule = list(schedule)
        state.last_fired.clear()
        state.one_shot_fired.clear()
        state.anchor_fired.clear()

    def add_schedule_entry(
        self, market: str, deposit: ScheduledDeposit
    ) -> None:
        """Append a single deposit to a market's schedule.

        Existing fired-state for prior entries is preserved.
        """
        if not isinstance(deposit, ScheduledDeposit):
            raise OperationalException(
                "BrokerBalanceTracker.add_schedule_entry: deposit must be a "
                f"ScheduledDeposit, got {type(deposit).__name__}."
            )
        self._get(market).schedule.append(deposit)

    def set_auto_sync(self, market: str, enabled: bool) -> None:
        self._get(market).auto_sync = enabled

    def is_auto_sync(self, market: str) -> bool:
        return self._get(market).auto_sync

    def set_auto_sync_error_mode(self, market: str, mode: str) -> None:
        """How auto-sync handles failures.

        * ``"raise"`` (default) — any sync error propagates and stops the
          event loop. Loud, recommended for development.
        * ``"warn"`` — log the error and continue with stale local state.
          Recommended for live trading where transient broker glitches
          should not crash the bot.
        * ``"halt"`` — log the error and halt only auto-sync for that
          market (the rest of the loop continues; manual
          ``context.sync_portfolio`` calls still work).
        """
        if mode not in _AUTO_SYNC_ERROR_MODES:
            raise OperationalException(
                f"auto_sync_error_mode must be one of "
                f"{_AUTO_SYNC_ERROR_MODES}, got {mode!r}."
            )
        self._get(market).auto_sync_error_mode = mode

    def get_auto_sync_error_mode(self, market: str) -> str:
        return self._get(market).auto_sync_error_mode

    def get_schedule(self, market: str) -> List[ScheduledDeposit]:
        return list(self._get(market).schedule)

    def fire_due_deposits(
        self,
        market: str,
        current_datetime: datetime,
        backtest_start: Optional[datetime] = None,
    ) -> float:
        """Advance the simulated broker clock to ``current_datetime``.

        Adds any deposits whose cadence has elapsed since the last fire to
        the market's pending balance and returns the **incremental** amount
        added during this call (useful for snapshot bookkeeping).

        Args:
            market: Market identifier.
            current_datetime: Simulated wall-clock time.
            backtest_start: Anchor for recurring deposits' first firing
                time. Defaults to ``current_datetime`` on the first call.
        """
        state = self._get(market)
        added = 0.0
        for idx, deposit in enumerate(state.schedule):
            if deposit.on is not None:
                if idx in state.one_shot_fired:
                    continue
                if deposit.on <= current_datetime:
                    state.pending += deposit.amount
                    state.one_shot_fired.add(idx)
                    added += deposit.amount
                    logger.info(
                        "Scheduled one-shot deposit fired on market %s: "
                        "%+.4f at %s",
                        market, deposit.amount, current_datetime,
                    )
                continue

            # Recurring
            delta = _interval_delta(deposit.time_unit, deposit.interval)
            anchor = state.last_fired.get(idx)
            if anchor is None:
                anchor = backtest_start or current_datetime
                state.last_fired[idx] = anchor
                if deposit.fire_on_anchor and idx not in state.anchor_fired:
                    state.pending += deposit.amount
                    state.anchor_fired.add(idx)
                    added += deposit.amount
                    logger.info(
                        "Scheduled recurring deposit fired (anchor) on "
                        "market %s: %+.4f at %s",
                        market, deposit.amount, anchor,
                    )
                # Don't fire at the anchor itself (unless fire_on_anchor);
                # next firing is at anchor + delta.
                continue

            while anchor + delta <= current_datetime:
                anchor = anchor + delta
                state.pending += deposit.amount
                added += deposit.amount
                logger.info(
                    "Scheduled recurring deposit fired on market %s: "
                    "%+.4f at %s",
                    market, deposit.amount, anchor,
                )
            state.last_fired[idx] = anchor
        return added

    def peek_pending(self, market: str) -> float:
        """Return the pending external balance without draining it."""
        return self._get(market).pending

    def consume_pending(self, market: str) -> float:
        """Atomically drain and return the pending external balance."""
        state = self._get(market)
        amount = state.pending
        state.pending = 0.0
        return amount

    def record_cash_flow(self, market: str, amount: float) -> None:
        """Record an absorbed external cash flow (deposit or withdrawal).

        Called by :meth:`Context.sync_portfolio` after a non-noop sync. The
        snapshot service drains this counter via :meth:`drain_cash_flow`
        each time it takes a snapshot so the snapshot's ``cash_flow``
        field reflects the deposits/withdrawals that landed *between* the
        previous snapshot and this one. This is what enables TWR-aware
        return metrics.
        """
        if amount == 0:
            return
        state = self._get(market)
        state.cash_flow_since_snapshot += float(amount)
        state.total_cash_flow += float(amount)

    def drain_cash_flow(self, market: str) -> float:
        """Atomically drain and return ``cash_flow_since_snapshot``."""
        state = self._get(market)
        amount = state.cash_flow_since_snapshot
        state.cash_flow_since_snapshot = 0.0
        return amount

    def total_cash_flow(self, market: str) -> float:
        """Lifetime sum of absorbed cash flow on ``market``."""
        return self._get(market).total_cash_flow

    def markets(self) -> List[str]:
        return list(self._markets.keys())

    def reset(self) -> None:
        """Wipe all state. Used when an app is reset between backtests."""
        self._markets.clear()

    def project_total(
        self,
        market: str,
        start: datetime,
        end: datetime,
    ) -> List[Tuple[datetime, float]]:
        """Compute the (timestamp, amount) deposits that would fire between
        ``start`` (exclusive) and ``end`` (inclusive) without mutating state.

        Used by the vector backtest, which is single-pass and applies
        deposits to its cash track up-front rather than tick-by-tick.
        """
        events: List[Tuple[datetime, float]] = []
        for deposit in self._get(market).schedule:
            if deposit.on is not None:
                if start < deposit.on <= end:
                    events.append((deposit.on, deposit.amount))
                continue
            delta = _interval_delta(deposit.time_unit, deposit.interval)
            if deposit.fire_on_anchor and start <= end:
                events.append((start, deposit.amount))
            t = start + delta
            while t <= end:
                events.append((t, deposit.amount))
                t = t + delta
        events.sort(key=lambda x: x[0])
        return events
