"""Tests for advanced BrokerBalanceTracker features added alongside the
``Context.sync_portfolio`` work: cash-flow recording, anchor-day firing,
case-insensitive market normalization, error-mode storage, and
``set_schedule`` mid-run state preservation.
"""
from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework import ScheduledDeposit, TimeUnit
from investing_algorithm_framework.domain.exceptions import (
    OperationalException,
)
from investing_algorithm_framework.services.portfolios \
    .broker_balance_tracker import BrokerBalanceTracker


def _utc(y, m, d, h=0):
    return datetime(y, m, d, h, tzinfo=timezone.utc)


class TestCashFlowRecording(TestCase):
    """``record_cash_flow`` / ``drain_cash_flow`` underpin the TWR
    snapshot path."""

    def test_record_and_drain(self):
        tracker = BrokerBalanceTracker()
        tracker.record_cash_flow("binance", 100.0)
        tracker.record_cash_flow("binance", -25.0)
        # Same market case-insensitive
        tracker.record_cash_flow("BINANCE", 5.0)

        # drain returns net cash flow since last drain and resets to 0
        self.assertEqual(80.0, tracker.drain_cash_flow("binance"))
        self.assertEqual(0.0, tracker.drain_cash_flow("binance"))

    def test_total_cash_flow_is_cumulative(self):
        tracker = BrokerBalanceTracker()
        tracker.record_cash_flow("binance", 100.0)
        tracker.drain_cash_flow("binance")
        tracker.record_cash_flow("binance", 50.0)
        # total_cash_flow keeps a running sum independent of drain
        self.assertEqual(150.0, tracker.total_cash_flow("binance"))

    def test_unknown_market_drain_is_zero(self):
        tracker = BrokerBalanceTracker()
        self.assertEqual(0.0, tracker.drain_cash_flow("unknown"))


class TestErrorModeStorage(TestCase):

    def test_default_is_raise(self):
        tracker = BrokerBalanceTracker()
        tracker.set_schedule("binance", [])
        self.assertEqual("raise", tracker.get_auto_sync_error_mode("binance"))

    def test_can_set_warn_or_halt(self):
        tracker = BrokerBalanceTracker()
        tracker.set_auto_sync_error_mode("binance", "warn")
        self.assertEqual("warn", tracker.get_auto_sync_error_mode("binance"))
        tracker.set_auto_sync_error_mode("binance", "halt")
        self.assertEqual("halt", tracker.get_auto_sync_error_mode("binance"))

    def test_invalid_mode_rejected(self):
        tracker = BrokerBalanceTracker()
        with self.assertRaises((ValueError, OperationalException)):
            tracker.set_auto_sync_error_mode("binance", "bogus")


class TestMarketNormalization(TestCase):

    def test_case_insensitive_keys(self):
        tracker = BrokerBalanceTracker()
        tracker.set_schedule(
            "binance",
            [ScheduledDeposit(amount=100.0, on=_utc(2024, 1, 5))],
        )
        # Anchor + fire under different casing
        tracker.fire_due_deposits("BINANCE", _utc(2024, 1, 1))
        tracker.fire_due_deposits("Binance", _utc(2024, 1, 6))
        # Peek with yet another casing
        self.assertEqual(100.0, tracker.peek_pending("binance"))
        self.assertTrue(tracker.has_market("BiNaNcE"))

    def test_none_market_raises(self):
        tracker = BrokerBalanceTracker()
        with self.assertRaises((ValueError, OperationalException)):
            tracker.set_schedule(None, [])


class TestSetScheduleMidRun(TestCase):

    def test_pending_and_cash_flow_preserved(self):
        tracker = BrokerBalanceTracker()
        tracker.set_schedule(
            "binance",
            [ScheduledDeposit(amount=100.0, on=_utc(2024, 1, 5))],
        )
        tracker.fire_due_deposits("binance", _utc(2024, 1, 1))
        tracker.fire_due_deposits("binance", _utc(2024, 1, 6))
        self.assertEqual(100.0, tracker.peek_pending("binance"))

        tracker.record_cash_flow("binance", 100.0)

        # Replace schedule mid-run
        tracker.set_schedule(
            "binance",
            [ScheduledDeposit(amount=200.0, on=_utc(2024, 2, 5))],
        )
        # Pending and cash_flow_since_snapshot must NOT be wiped
        self.assertEqual(100.0, tracker.peek_pending("binance"))
        self.assertEqual(100.0, tracker.drain_cash_flow("binance"))


class TestFireOnAnchor(TestCase):

    def test_recurring_with_fire_on_anchor_fires_immediately(self):
        tracker = BrokerBalanceTracker()
        deposit = ScheduledDeposit(
            amount=50.0,
            interval=14,
            time_unit=TimeUnit.DAY,
            fire_on_anchor=True,
        )
        tracker.set_schedule("binance", [deposit])
        # Anchor itself should fire
        tracker.fire_due_deposits(
            "binance", _utc(2024, 1, 1), backtest_start=_utc(2024, 1, 1)
        )
        self.assertEqual(50.0, tracker.peek_pending("binance"))

    def test_recurring_without_fire_on_anchor_does_not_fire_at_anchor(self):
        tracker = BrokerBalanceTracker()
        deposit = ScheduledDeposit(
            amount=50.0,
            interval=14,
            time_unit=TimeUnit.DAY,
        )
        tracker.set_schedule("binance", [deposit])
        tracker.fire_due_deposits(
            "binance", _utc(2024, 1, 1), backtest_start=_utc(2024, 1, 1)
        )
        self.assertEqual(0.0, tracker.peek_pending("binance"))
        # Next interval (Jan 15) does fire
        tracker.fire_due_deposits("binance", _utc(2024, 1, 15))
        self.assertEqual(50.0, tracker.peek_pending("binance"))

    def test_fire_on_anchor_rejected_for_one_shot(self):
        with self.assertRaises(ValueError):
            ScheduledDeposit(
                amount=50.0, on=_utc(2024, 1, 1), fire_on_anchor=True
            )


class TestProjectTotalAnchor(TestCase):

    def test_project_total_includes_anchor_when_flagged(self):
        tracker = BrokerBalanceTracker()
        d = ScheduledDeposit(
            amount=100.0,
            interval=30,
            time_unit=TimeUnit.DAY,
            fire_on_anchor=True,
        )
        tracker.set_schedule("binance", [d])
        # 60 days from anchor, fire_on_anchor=True ⇒ 3 fires (day 0, 30, 60)
        events = tracker.project_total(
            "binance", _utc(2024, 1, 1), _utc(2024, 3, 1)
        )
        total = sum(amount for _, amount in events)
        self.assertEqual(300.0, total)

    def test_project_total_excludes_anchor_by_default(self):
        tracker = BrokerBalanceTracker()
        d = ScheduledDeposit(
            amount=100.0,
            interval=30,
            time_unit=TimeUnit.DAY,
        )
        tracker.set_schedule("binance", [d])
        # 60 days from anchor, fire_on_anchor=False ⇒ 2 fires (day 30, 60)
        events = tracker.project_total(
            "binance", _utc(2024, 1, 1), _utc(2024, 3, 1)
        )
        total = sum(amount for _, amount in events)
        self.assertEqual(200.0, total)
