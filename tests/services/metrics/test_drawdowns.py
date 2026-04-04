import unittest
import random
from datetime import datetime, timedelta
from unittest.mock import MagicMock
from investing_algorithm_framework import get_drawdown_series, \
    get_max_drawdown, get_max_drawdown_absolute, get_max_daily_drawdown, \
    get_max_drawdown_duration


def _make_snapshots(timestamps, values):
    """Helper to create mock PortfolioSnapshot objects."""
    snapshots = []
    for ts, val in zip(timestamps, values):
        snapshot = MagicMock()
        snapshot.created_at = ts
        snapshot.total_value = val
        snapshots.append(snapshot)
    return snapshots


class TestDrawdownFunctions(unittest.TestCase):

    def setUp(self):
        # Generate mocked equity curve: net_size over time
        self.timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
            datetime(2024, 1, 4),
            datetime(2024, 1, 5),
        ]

        self.net_sizes = [1000, 1200, 900, 1100, 1300]  # Simulates rise, fall, recovery, new high

        # Create mock snapshot objects
        self.snapshots = []
        for ts, net_size in zip(self.timestamps, self.net_sizes):
            snapshot = MagicMock()
            snapshot.created_at = ts
            snapshot.total_value = net_size
            self.snapshots.append(snapshot)

        # Create a mocked BacktestReport
        self.backtest_result = MagicMock()
        self.backtest_result.portfolio_snapshots = self.snapshots

    def test_drawdown_series(self):
        drawdown_series = get_drawdown_series(self.backtest_result.portfolio_snapshots)
        expected_drawdowns = [
            0.0,                                # baseline
            0.0,                                # new high
            (900 - 1200) / 1200,                # drop from peak
            (1100 - 1200) / 1200,               # partial recovery
            0.0                                 # new peak again
        ]

        self.assertEqual(len(drawdown_series), len(expected_drawdowns))

        for i, (drawdown, _) in enumerate(drawdown_series):
            self.assertAlmostEqual(drawdown, expected_drawdowns[i], places=6)

    def test_max_drawdown(self):
        max_drawdown = get_max_drawdown(self.backtest_result.portfolio_snapshots)
        expected_max = abs((900 - 1200) / 1200) # 0.25
        self.assertAlmostEqual(max_drawdown, expected_max, places=6)

    def test_max_drawdown_absolute(self):
        max_drawdown = get_max_drawdown_absolute(self.backtest_result.portfolio_snapshots)
        self.assertEqual(max_drawdown, 300)  # 1200 - 900 = 300


class TestGetMaxDailyDrawdown(unittest.TestCase):
    """Tests for get_max_daily_drawdown — worst single-day decline."""

    def test_worst_daily_decline_differs_from_max_drawdown(self):
        """
        Max daily decline should be the worst single-day return,
        not the peak-to-trough drawdown.

        Equity:  [1000, 950, 900, 1100, 1300]
        Daily returns: -5%, -5.26%, +22.2%, +18.2%
        Worst daily: -5.26% (950→900)
        Peak-to-trough: -10% (1000→900)
        """
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
            datetime(2024, 1, 4),
            datetime(2024, 1, 5),
        ]
        values = [1000, 950, 900, 1100, 1300]
        snapshots = _make_snapshots(timestamps, values)

        result = get_max_daily_drawdown(snapshots)
        # Worst single-day: (900 - 950) / 950 ≈ -0.05263
        expected = abs((900 - 950) / 950)
        self.assertAlmostEqual(result, expected, places=4)

    def test_larger_daily_drop_in_middle(self):
        """
        When the largest single-day drop is not the overall trough.

        Equity:  [1000, 1200, 1100, 900, 1300]
        Daily returns: +20%, -8.33%, -18.18%, +44.4%
        Worst daily: -18.18% (1100→900)
        Peak-to-trough: -25% (1200→900)
        """
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
            datetime(2024, 1, 4),
            datetime(2024, 1, 5),
        ]
        values = [1000, 1200, 1100, 900, 1300]
        snapshots = _make_snapshots(timestamps, values)

        result = get_max_daily_drawdown(snapshots)
        expected = abs((900 - 1100) / 1100)  # ≈ 0.1818
        self.assertAlmostEqual(result, expected, places=4)

    def test_all_positive_returns(self):
        """
        When all daily returns are positive, there is no decline,
        so max daily drawdown should be 0.

        The function should only consider negative day-over-day returns.
        """
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
            datetime(2024, 1, 4),
        ]
        values = [1000, 1100, 1200, 1400]
        snapshots = _make_snapshots(timestamps, values)

        result = get_max_daily_drawdown(snapshots)
        # No negative returns exist → worst daily drawdown = 0
        self.assertAlmostEqual(result, 0.0, places=6,
            msg="All-positive returns should yield 0 drawdown")

    def test_single_snapshot(self):
        """Single snapshot means no daily return — drawdown should be 0."""
        snapshots = _make_snapshots(
            [datetime(2024, 1, 1)], [1000]
        )
        result = get_max_daily_drawdown(snapshots)
        self.assertEqual(result, 0.0)

    def test_resamples_intraday_to_daily(self):
        """
        Multiple intra-day snapshots should be resampled to daily
        (last value of the day).

        Raw:  Day1 9am=1000, Day1 3pm=1200, Day2 9am=1100, Day3 9am=900
        Daily (last): [1200, 1100, 900]
        Daily returns: -8.33%, -18.18%
        Worst daily: -18.18%  (NOT peak-to-trough of -25%)
        """
        timestamps = [
            datetime(2024, 1, 1, 9, 0),
            datetime(2024, 1, 1, 15, 0),
            datetime(2024, 1, 2, 9, 0),
            datetime(2024, 1, 3, 9, 0),
        ]
        values = [1000, 1200, 1100, 900]
        snapshots = _make_snapshots(timestamps, values)

        result = get_max_daily_drawdown(snapshots)
        # After resample: [1200, 1100, 900]
        # Worst day-over-day return: (900 - 1100) / 1100 = -0.1818
        expected = abs((900 - 1100) / 1100)
        self.assertAlmostEqual(result, expected, places=4)

    def test_flat_equity(self):
        """Constant equity means no daily changes — drawdown = 0."""
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
        ]
        values = [1000, 1000, 1000]
        snapshots = _make_snapshots(timestamps, values)

        result = get_max_daily_drawdown(snapshots)
        self.assertEqual(result, 0.0)


class TestGetMaxDrawdownDuration(unittest.TestCase):
    """Tests for get_max_drawdown_duration — drawdown duration in actual days."""

    def test_daily_snapshots_duration(self):
        """
        With daily snapshots, drawdown duration should be in calendar days.

        Equity: [1000, 1200, 900, 1000, 1100, 1100, 1300]
        Dates:   Jan1  Jan2  Jan3  Jan4   Jan5   Jan6   Jan7
        Peak at Jan 2 (1200). Below peak: Jan 3-6. Recovery: Jan 7.
        """
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
            datetime(2024, 1, 4),
            datetime(2024, 1, 5),
            datetime(2024, 1, 6),
            datetime(2024, 1, 7),
        ]
        values = [1000, 1200, 900, 1000, 1100, 1100, 1300]
        snapshots = _make_snapshots(timestamps, values)

        result = get_max_drawdown_duration(snapshots)
        # With daily data, 4 snapshots below peak = 4 calendar days
        self.assertGreaterEqual(result, 4)

    def test_weekly_snapshots_returns_days_not_snapshot_count(self):
        """
        With weekly snapshots, should return calendar days, NOT snapshot count.

        Equity: [1000, 1200, 900, 1100, 1300]
        Dates:   Jan1  Jan8  Jan15 Jan22 Jan29  (weekly)
        Peak at Jan 8 (1200). Below peak: Jan 15, Jan 22. Recovery: Jan 29.
        Buggy code returns 2 (snapshot count).
        Fixed code should return days: ≥7 (e.g. 14 or 21 depending on measurement).
        """
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 8),
            datetime(2024, 1, 15),
            datetime(2024, 1, 22),
            datetime(2024, 1, 29),
        ]
        values = [1000, 1200, 900, 1100, 1300]
        snapshots = _make_snapshots(timestamps, values)

        result = get_max_drawdown_duration(snapshots)
        self.assertGreater(
            result, 2,
            "Duration should be in calendar days, not snapshot count"
        )

    def test_no_drawdown(self):
        """Monotonically increasing equity has no drawdown — duration = 0."""
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
        ]
        values = [1000, 1100, 1200]
        snapshots = _make_snapshots(timestamps, values)

        result = get_max_drawdown_duration(snapshots)
        self.assertEqual(result, 0)

    def test_drawdown_extends_to_end_of_series(self):
        """
        If the portfolio never recovers, the drawdown extends to the last
        snapshot and should be measured in calendar days.

        Equity: [1000, 800, 700, 900]
        Dates:   Jan1  Jan8  Jan15 Jan22  (weekly)
        Peak at Jan 1. Never recovered.
        Buggy: returns 3 (snapshot count).
        Fixed: should return ≥14 (calendar days from Jan 1 to Jan 22).
        """
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 8),
            datetime(2024, 1, 15),
            datetime(2024, 1, 22),
        ]
        values = [1000, 800, 700, 900]
        snapshots = _make_snapshots(timestamps, values)

        result = get_max_drawdown_duration(snapshots)
        self.assertGreater(
            result, 3,
            "Duration should be in calendar days, not snapshot count"
        )

    def test_multiple_drawdown_periods_returns_longest(self):
        """
        When there are multiple drawdown periods, return the longest one
        in calendar days.

        Equity: [1000, 900, 1100, 1050, 1000, 900, 1200]
        Dates:   Jan1  Jan2  Jan3   Jan10  Jan17  Jan24  Jan31
        Drawdown 1: Jan 1→Jan 2 (1 day, 1 snapshot below peak)
        Drawdown 2: Jan 3 peak (1100), below: Jan 10, Jan 17, Jan 24
                    Recovery: Jan 31. Duration = 21+ days in calendar time.
        """
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
            datetime(2024, 1, 10),
            datetime(2024, 1, 17),
            datetime(2024, 1, 24),
            datetime(2024, 1, 31),
        ]
        values = [1000, 900, 1100, 1050, 1000, 900, 1200]
        snapshots = _make_snapshots(timestamps, values)

        result = get_max_drawdown_duration(snapshots)
        # Second drawdown period is the longest: 3 snapshots below peak
        # but 21+ calendar days. Must be greater than snapshot count.
        self.assertGreater(
            result, 3,
            "Duration should be in calendar days, not snapshot count"
        )

    def test_empty_snapshots(self):
        """Empty snapshot list should return 0."""
        result = get_max_drawdown_duration([])
        self.assertEqual(result, 0)


class TestDrawdownConsistency(unittest.TestCase):
    """Verify equity curve sort order and metric consistency."""

    def test_unsorted_snapshots_produce_same_drawdown_as_sorted(self):
        """
        Shuffled snapshots should produce the same max_drawdown
        as chronologically sorted snapshots (functions should sort
        internally or the equity curve should be timestamp-ordered).
        """
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
            datetime(2024, 1, 4),
            datetime(2024, 1, 5),
        ]
        values = [1000, 1200, 900, 1100, 1300]

        sorted_snapshots = _make_snapshots(timestamps, values)

        pairs = list(zip(timestamps, values))
        random.seed(42)
        random.shuffle(pairs)
        shuffled_ts, shuffled_vals = zip(*pairs)
        shuffled_snapshots = _make_snapshots(shuffled_ts, shuffled_vals)

        sorted_result = get_max_drawdown(sorted_snapshots)
        shuffled_result = get_max_drawdown(shuffled_snapshots)

        self.assertAlmostEqual(sorted_result, shuffled_result, places=6)

    def test_max_drawdown_matches_manual_computation_from_total_value(self):
        """
        Max drawdown from the equity curve should match a manual
        computation from the snapshot total_value fields.
        """
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
            datetime(2024, 1, 4),
            datetime(2024, 1, 5),
        ]
        values = [1000, 1200, 900, 1100, 1300]
        snapshots = _make_snapshots(timestamps, values)

        # Manual: peak = 1200, trough = 900
        # Max drawdown = (1200 - 900) / 1200 = 0.25
        expected = 0.25
        result = get_max_drawdown(snapshots)
        self.assertAlmostEqual(result, expected, places=6)

    def test_drawdown_series_timestamps_match_snapshots(self):
        """
        The drawdown series timestamps should correspond to the
        snapshot timestamps.
        """
        timestamps = [
            datetime(2024, 1, 1),
            datetime(2024, 1, 2),
            datetime(2024, 1, 3),
        ]
        values = [1000, 900, 1100]
        snapshots = _make_snapshots(timestamps, values)

        drawdown_series = get_drawdown_series(snapshots)
        self.assertEqual(len(drawdown_series), len(timestamps))

        for (_, ts), expected_ts in zip(drawdown_series, timestamps):
            self.assertEqual(ts, expected_ts)
