"""Tests for the v9.0 scheduling primitives (issue #441)."""
from datetime import date, datetime, timedelta, timezone
from unittest import TestCase

from investing_algorithm_framework import (
    DateRule,
    Schedule,
    ScheduledFunction,
    TimeRule,
    TimeUnit,
)


# ----------------------------------------------------------------------
# DateRule
# ----------------------------------------------------------------------


class TestDateRule(TestCase):

    def test_every_day_matches_all_days_without_calendar(self):
        rule = DateRule.every_day()
        for d in (date(2025, 1, 1), date(2025, 3, 15), date(2025, 12, 31)):
            self.assertTrue(rule.matches(d))

    def test_week_start_matches_monday_by_default(self):
        rule = DateRule.week_start()
        self.assertTrue(rule.matches(date(2025, 1, 6)))   # Monday
        self.assertFalse(rule.matches(date(2025, 1, 7)))  # Tuesday

    def test_week_start_with_offset(self):
        rule = DateRule.week_start(days_offset=2)
        self.assertTrue(rule.matches(date(2025, 1, 8)))   # Wednesday
        self.assertFalse(rule.matches(date(2025, 1, 6)))

    def test_week_end_matches_sunday_by_default(self):
        rule = DateRule.week_end()
        self.assertTrue(rule.matches(date(2025, 1, 12)))  # Sunday
        self.assertFalse(rule.matches(date(2025, 1, 11)))

    def test_week_end_with_offset(self):
        rule = DateRule.week_end(days_offset=2)
        self.assertTrue(rule.matches(date(2025, 1, 10)))  # Friday

    def test_month_start_matches_first_day(self):
        rule = DateRule.month_start()
        self.assertTrue(rule.matches(date(2025, 3, 1)))
        self.assertFalse(rule.matches(date(2025, 3, 2)))

    def test_month_start_with_offset(self):
        rule = DateRule.month_start(days_offset=5)
        self.assertTrue(rule.matches(date(2025, 3, 6)))

    def test_month_end_matches_last_day(self):
        rule = DateRule.month_end()
        self.assertTrue(rule.matches(date(2025, 2, 28)))  # Feb non-leap
        self.assertTrue(rule.matches(date(2024, 2, 29)))  # Feb leap
        self.assertTrue(rule.matches(date(2025, 3, 31)))
        self.assertFalse(rule.matches(date(2025, 3, 30)))

    def test_month_end_with_offset(self):
        rule = DateRule.month_end(days_offset=1)
        self.assertTrue(rule.matches(date(2025, 3, 30)))

    def test_negative_offsets_rejected(self):
        for ctor in (
            DateRule.week_start,
            DateRule.week_end,
            DateRule.month_start,
            DateRule.month_end,
        ):
            with self.assertRaises(ValueError):
                ctor(days_offset=-1)


# ----------------------------------------------------------------------
# TimeRule
# ----------------------------------------------------------------------


class TestTimeRule(TestCase):

    def test_at_returns_single_time(self):
        rule = TimeRule.at(9, 30)
        times = rule.times_for(date(2025, 1, 1))
        self.assertEqual(len(times), 1)
        self.assertEqual(times[0].hour, 9)
        self.assertEqual(times[0].minute, 30)

    def test_at_with_seconds(self):
        rule = TimeRule.at(15, 45, 30)
        t = rule.times_for(date(2025, 1, 1))[0]
        self.assertEqual((t.hour, t.minute, t.second), (15, 45, 30))

    def test_at_validates_bounds(self):
        with self.assertRaises(ValueError):
            TimeRule.at(24)
        with self.assertRaises(ValueError):
            TimeRule.at(0, 60)
        with self.assertRaises(ValueError):
            TimeRule.at(0, 0, 60)
        with self.assertRaises(ValueError):
            TimeRule.at(-1)

    def test_market_open_requires_calendar(self):
        rule = TimeRule.market_open(minutes=15)
        with self.assertRaises(NotImplementedError) as ctx:
            rule.times_for(date(2025, 1, 1))
        self.assertIn("TradingCalendar", str(ctx.exception))
        self.assertIn("#444", str(ctx.exception))

    def test_market_close_requires_calendar(self):
        rule = TimeRule.market_close(minutes=15)
        with self.assertRaises(NotImplementedError):
            rule.times_for(date(2025, 1, 1))

    def test_every_minute_requires_calendar(self):
        rule = TimeRule.every_minute()
        with self.assertRaises(NotImplementedError):
            rule.times_for(date(2025, 1, 1))

    def test_market_relative_rejects_negative_offset(self):
        with self.assertRaises(ValueError):
            TimeRule.market_open(minutes=-1)
        with self.assertRaises(ValueError):
            TimeRule.market_close(minutes=-1)


# ----------------------------------------------------------------------
# Schedule
# ----------------------------------------------------------------------


class TestScheduleInterval(TestCase):

    def test_every_factory(self):
        s = Schedule.every(2, TimeUnit.HOUR)
        self.assertTrue(s.is_interval)
        self.assertFalse(s.is_rule_based)
        self.assertEqual(s.step(), timedelta(hours=2))

    def test_step_for_all_units(self):
        self.assertEqual(
            Schedule.every(30, TimeUnit.SECOND).step(),
            timedelta(seconds=30),
        )
        self.assertEqual(
            Schedule.every(5, TimeUnit.MINUTE).step(),
            timedelta(minutes=5),
        )
        self.assertEqual(
            Schedule.every(1, TimeUnit.DAY).step(),
            timedelta(days=1),
        )

    def test_interval_must_be_positive(self):
        with self.assertRaises(ValueError):
            Schedule.every(0, TimeUnit.HOUR)
        with self.assertRaises(ValueError):
            Schedule.every(-1, TimeUnit.HOUR)

    def test_iter_run_times_yields_evenly_spaced(self):
        s = Schedule.every(1, TimeUnit.HOUR)
        start = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2025, 1, 1, 3, 0, tzinfo=timezone.utc)
        times = list(s.iter_run_times(start, end))
        self.assertEqual(len(times), 4)
        self.assertEqual(times[0], start)
        self.assertEqual(times[-1], end)

    def test_is_due_interval_first_call(self):
        s = Schedule.every(1, TimeUnit.HOUR)
        now = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(s.is_due(now, last_run=None))

    def test_is_due_interval_respects_step(self):
        s = Schedule.every(1, TimeUnit.HOUR)
        last = datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)
        # 30 min later — not due.
        self.assertFalse(
            s.is_due(
                last + timedelta(minutes=30), last_run=last
            )
        )
        # 60 min later — due.
        self.assertTrue(
            s.is_due(
                last + timedelta(minutes=60), last_run=last
            )
        )

    def test_default_anchor_aligns_to_epoch_utc_boundaries(self):
        # Every 2 hours, no explicit anchor -> 00:00, 02:00, ...,
        # 08:00, 10:00, 12:00 UTC, matching whole-clock expectations.
        s = Schedule.every(2, TimeUnit.HOUR)
        after = datetime(2025, 1, 1, 8, 30, tzinfo=timezone.utc)
        self.assertEqual(
            s.next_run_after(after),
            datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )

    def test_custom_anchor_shifts_the_grid(self):
        anchor = datetime(2025, 1, 1, 9, 30, tzinfo=timezone.utc)
        s = Schedule.every(2, TimeUnit.HOUR, anchor=anchor)
        after = datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc)
        # Grid is 09:30, 11:30, 13:30, ... regardless of the date.
        self.assertEqual(
            s.next_run_after(after),
            datetime(2025, 1, 1, 11, 30, tzinfo=timezone.utc),
        )

    def test_manual_run_mid_slot_does_not_shift_next_natural_run(self):
        # A forced/manual run recorded partway through a slot must not
        # push the next natural run later — the fixed grid boundary
        # (10:00) stays due regardless of the manual run at 08:45.
        s = Schedule.every(2, TimeUnit.HOUR)
        manual_run_at = datetime(2025, 1, 1, 8, 45, tzinfo=timezone.utc)

        # Immediately after the manual run, not yet due again.
        self.assertFalse(
            s.is_due(
                manual_run_at + timedelta(minutes=1),
                last_run=manual_run_at,
            )
        )
        # At the next fixed slot boundary (10:00), due again.
        self.assertTrue(
            s.is_due(
                datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
                last_run=manual_run_at,
            )
        )
        self.assertEqual(
            s.next_run_after(manual_run_at),
            datetime(2025, 1, 1, 10, 0, tzinfo=timezone.utc),
        )


class TestScheduleRuleBased(TestCase):

    def test_on_factory(self):
        s = Schedule.on(
            DateRule.month_start(), TimeRule.at(9, 30)
        )
        self.assertTrue(s.is_rule_based)
        self.assertFalse(s.is_interval)
        self.assertIsNone(s.step())

    def test_iter_run_times_monthly(self):
        s = Schedule.on(
            DateRule.month_start(), TimeRule.at(9, 30)
        )
        start = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2025, 6, 30, 23, 59, tzinfo=timezone.utc)
        times = list(s.iter_run_times(start, end))
        self.assertEqual(len(times), 6)
        for t in times:
            self.assertEqual(t.day, 1)
            self.assertEqual((t.hour, t.minute), (9, 30))

    def test_iter_run_times_weekly(self):
        s = Schedule.on(
            DateRule.week_start(), TimeRule.at(8, 0)
        )
        start = datetime(2025, 1, 1, 0, 0, tzinfo=timezone.utc)
        end = datetime(2025, 1, 31, 23, 59, tzinfo=timezone.utc)
        times = list(s.iter_run_times(start, end))
        # Mondays in Jan 2025: 6, 13, 20, 27.
        self.assertEqual([t.day for t in times], [6, 13, 20, 27])

    def test_is_due_rule_based_matches(self):
        s = Schedule.on(
            DateRule.month_start(), TimeRule.at(9, 30)
        )
        now = datetime(2025, 3, 1, 10, 0, tzinfo=timezone.utc)
        self.assertTrue(s.is_due(now, last_run=None))

    def test_is_due_rule_based_does_not_refire_same_day(self):
        s = Schedule.on(
            DateRule.month_start(), TimeRule.at(9, 30)
        )
        last = datetime(2025, 3, 1, 9, 30, tzinfo=timezone.utc)
        # Same day, later — should not refire.
        self.assertFalse(
            s.is_due(
                last + timedelta(hours=2), last_run=last
            )
        )

    def test_is_due_rule_based_wrong_day(self):
        s = Schedule.on(
            DateRule.month_start(), TimeRule.at(9, 30)
        )
        now = datetime(2025, 3, 15, 9, 30, tzinfo=timezone.utc)
        self.assertFalse(s.is_due(now, last_run=None))


class TestScheduleValidation(TestCase):

    def test_rejects_both_modes(self):
        with self.assertRaises(ValueError):
            Schedule(
                time_unit=TimeUnit.HOUR,
                interval=1,
                date_rule=DateRule.every_day(),
                time_rule=TimeRule.at(9, 30),
            )

    def test_rejects_neither_mode(self):
        with self.assertRaises(ValueError):
            Schedule()

    def test_rejects_partial_interval(self):
        with self.assertRaises(ValueError):
            Schedule(time_unit=TimeUnit.HOUR)
        with self.assertRaises(ValueError):
            Schedule(interval=2)


# ----------------------------------------------------------------------
# ScheduledFunction
# ----------------------------------------------------------------------


class TestScheduledFunction(TestCase):

    def test_explicit_schedule(self):
        sched = Schedule.every(1, TimeUnit.DAY)
        sf = ScheduledFunction(func="rebalance", schedule=sched)
        self.assertEqual(sf.func, "rebalance")
        self.assertIs(sf.schedule, sched)

    def test_shorthand_builds_schedule(self):
        sf = ScheduledFunction(
            func="rebalance",
            date_rule=DateRule.month_start(),
            time_rule=TimeRule.at(9, 30),
        )
        self.assertTrue(sf.schedule.is_rule_based)

    def test_explicit_and_shorthand_mutually_exclusive(self):
        with self.assertRaises(ValueError):
            ScheduledFunction(
                func="rebalance",
                schedule=Schedule.every(1, TimeUnit.DAY),
                date_rule=DateRule.every_day(),
            )

    def test_shorthand_requires_both_rules(self):
        with self.assertRaises(ValueError):
            ScheduledFunction(
                func="rebalance",
                date_rule=DateRule.every_day(),
            )

    def test_func_must_be_non_empty_string(self):
        with self.assertRaises(ValueError):
            ScheduledFunction(
                func="", schedule=Schedule.every(1, TimeUnit.DAY)
            )
