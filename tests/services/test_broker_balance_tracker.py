"""Unit tests for BrokerBalanceTracker."""
from datetime import datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework import ScheduledDeposit, TimeUnit
from investing_algorithm_framework.services.portfolios \
    .broker_balance_tracker import BrokerBalanceTracker


def _utc(year, month, day, hour=0):
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


class TestBrokerBalanceTracker(TestCase):

    def test_pending_starts_at_zero(self):
        tracker = BrokerBalanceTracker()
        self.assertEqual(0.0, tracker.peek_pending("BITVAVO"))

    def test_consume_pending_drains_to_zero(self):
        tracker = BrokerBalanceTracker()
        tracker.set_schedule(
            "BITVAVO",
            [ScheduledDeposit(amount=50.0, on=_utc(2024, 1, 5))],
        )
        # Anchor (no deposits before this point)
        tracker.fire_due_deposits("BITVAVO", _utc(2024, 1, 1))
        # After the one-shot fires
        tracker.fire_due_deposits("BITVAVO", _utc(2024, 1, 6))
        self.assertEqual(50.0, tracker.peek_pending("BITVAVO"))
        self.assertEqual(50.0, tracker.consume_pending("BITVAVO"))
        self.assertEqual(0.0, tracker.peek_pending("BITVAVO"))

    def test_recurring_deposit_fires_on_cadence(self):
        tracker = BrokerBalanceTracker()
        tracker.set_schedule(
            "BITVAVO",
            [
                ScheduledDeposit(
                    amount=100.0,
                    time_unit=TimeUnit.DAY,
                    interval=30,
                ),
            ],
        )
        # Anchor at start; first firing must be at start + 30d.
        tracker.fire_due_deposits("BITVAVO", _utc(2024, 1, 1))
        self.assertEqual(0.0, tracker.peek_pending("BITVAVO"))
        # Halfway: still nothing.
        tracker.fire_due_deposits("BITVAVO", _utc(2024, 1, 15))
        self.assertEqual(0.0, tracker.peek_pending("BITVAVO"))
        # Past first cadence boundary: one firing.
        tracker.fire_due_deposits("BITVAVO", _utc(2024, 2, 1))
        self.assertEqual(100.0, tracker.peek_pending("BITVAVO"))
        # Skip ahead 65 days from start: should now be 2 total firings.
        tracker.fire_due_deposits(
            "BITVAVO", _utc(2024, 1, 1) + timedelta(days=65)
        )
        self.assertEqual(200.0, tracker.peek_pending("BITVAVO"))

    def test_one_shot_only_fires_once(self):
        tracker = BrokerBalanceTracker()
        tracker.set_schedule(
            "BITVAVO",
            [ScheduledDeposit(amount=500.0, on=_utc(2024, 6, 15))],
        )
        tracker.fire_due_deposits("BITVAVO", _utc(2024, 1, 1))
        tracker.fire_due_deposits("BITVAVO", _utc(2024, 7, 1))
        tracker.fire_due_deposits("BITVAVO", _utc(2024, 8, 1))
        self.assertEqual(500.0, tracker.peek_pending("BITVAVO"))

    def test_negative_recurring_deposit_is_withdrawal(self):
        tracker = BrokerBalanceTracker()
        tracker.set_schedule(
            "BITVAVO",
            [
                ScheduledDeposit(
                    amount=-25.0,
                    time_unit=TimeUnit.DAY,
                    interval=7,
                ),
            ],
        )
        tracker.fire_due_deposits("BITVAVO", _utc(2024, 1, 1))
        tracker.fire_due_deposits("BITVAVO", _utc(2024, 1, 22))
        # 3 weeks -> 3 firings of -25 = -75
        self.assertEqual(-75.0, tracker.peek_pending("BITVAVO"))

    def test_auto_sync_default_off(self):
        tracker = BrokerBalanceTracker()
        self.assertFalse(tracker.is_auto_sync("BITVAVO"))
        tracker.set_auto_sync("BITVAVO", True)
        self.assertTrue(tracker.is_auto_sync("BITVAVO"))

    def test_project_total_yields_sorted_events(self):
        tracker = BrokerBalanceTracker()
        tracker.set_schedule(
            "BITVAVO",
            [
                ScheduledDeposit(
                    amount=100.0, time_unit=TimeUnit.DAY, interval=30
                ),
                ScheduledDeposit(amount=500.0, on=_utc(2024, 2, 15)),
            ],
        )
        events = tracker.project_total(
            market="BITVAVO",
            start=_utc(2024, 1, 1),
            end=_utc(2024, 4, 1),
        )
        self.assertEqual(
            [
                (_utc(2024, 1, 31), 100.0),
                (_utc(2024, 2, 15), 500.0),
                (_utc(2024, 3, 1), 100.0),
                (_utc(2024, 3, 31), 100.0),
            ],
            events,
        )

    def test_set_schedule_replaces_state(self):
        tracker = BrokerBalanceTracker()
        tracker.set_schedule(
            "BITVAVO",
            [ScheduledDeposit(amount=10.0, on=_utc(2024, 1, 5))],
        )
        tracker.fire_due_deposits("BITVAVO", _utc(2024, 1, 6))
        self.assertEqual(10.0, tracker.peek_pending("BITVAVO"))
        tracker.set_schedule(
            "BITVAVO",
            [ScheduledDeposit(amount=99.0, on=_utc(2024, 2, 5))],
        )
        # Pending balance is preserved (it represents already-credited
        # external cash, separate from the schedule itself).
        self.assertEqual(10.0, tracker.peek_pending("BITVAVO"))
        # But the original one-shot's "fired" flag is reset, so the new
        # schedule operates independently.
        tracker.fire_due_deposits("BITVAVO", _utc(2024, 2, 6))
        self.assertEqual(109.0, tracker.peek_pending("BITVAVO"))


class TestScheduledDepositValidation(TestCase):

    def test_rejects_no_schedule(self):
        with self.assertRaises(ValueError):
            ScheduledDeposit(amount=10.0)

    def test_rejects_mixed_schedule(self):
        with self.assertRaises(ValueError):
            ScheduledDeposit(
                amount=10.0,
                time_unit=TimeUnit.DAY,
                interval=1,
                on=_utc(2024, 1, 1),
            )

    def test_rejects_partial_recurring(self):
        with self.assertRaises(ValueError):
            ScheduledDeposit(amount=10.0, time_unit=TimeUnit.DAY)
        with self.assertRaises(ValueError):
            ScheduledDeposit(amount=10.0, interval=5)

    def test_rejects_non_positive_interval(self):
        with self.assertRaises(ValueError):
            ScheduledDeposit(
                amount=10.0, time_unit=TimeUnit.DAY, interval=0
            )
