"""Regression tests for ``Backtest.regenerate_summaries()``.

These tests lock the contract that the per-engine summary slots
(``vector_summary`` / ``event_summary``) are recomputed *only* from
that engine's run list, and that the resulting absolute / count
metrics match the documented aggregation rules in
:func:`generate_backtest_summary_metrics` (sums for absolutes, weighted
means for ratios, mins for drawdowns).

Motivation: notebook 03's "summary net gain" panel reads
``backtest.get_summary("vector").total_net_gain``. We want a
deterministic test that pins that value down, independent of any
engine simulation, so changes to the aggregation rules surface
immediately rather than as silent metric drift in tutorials.
"""
from datetime import datetime, timezone
from unittest import TestCase

from investing_algorithm_framework import Backtest
from investing_algorithm_framework.domain import BacktestWindow, BacktestDateRange
from investing_algorithm_framework.domain import (
    BacktestRun,
    BacktestMetrics,
    PortfolioSnapshot,
)


def _snapshots():
    return [
        PortfolioSnapshot(
            created_at="2023-01-01 00:00:00",
            total_value=1000,
            trading_symbol="EUR",
            unallocated=1000,
        ),
        PortfolioSnapshot(
            created_at="2023-04-01 00:00:00",
            total_value=1100,
            trading_symbol="EUR",
            unallocated=100,
        ),
    ]


def _make_run(start, end, *, gain, trades, days=120, sharpe=1.5):
    """Build a minimal ``BacktestRun`` carrying explicit
    ``BacktestMetrics`` so we can assert against the aggregator."""
    window = BacktestWindow(
        train_range=BacktestDateRange(
            start_date=start,
            end_date=end,
            name=f"{start:%Y%m%d}-{end:%Y%m%d}",
        )
    )
    return BacktestRun(
        backtest_window=window,
        created_at=datetime.now(tz=timezone.utc),
        orders=[],
        trades=[],
        positions=[],
        portfolio_snapshots=_snapshots(),
        data_sources=[],
        number_of_runs=1,
        initial_unallocated=1000,
        backtest_metrics=BacktestMetrics(
            backtest_window=window,
            total_net_gain=gain,
            total_net_gain_percentage=gain / 1000.0,
            total_growth=gain,
            total_growth_percentage=gain / 1000.0,
            number_of_trades=trades,
            number_of_trades_closed=trades,
            win_rate=0.6,
            gross_profit=max(gain, 0),
            gross_loss=abs(min(gain, 0)),
            sharpe_ratio=sharpe,
            sortino_ratio=sharpe + 0.5,
            cagr=gain / 1000.0,
            max_drawdown=-0.05,
            total_number_of_days=days,
        ),
    )


class TestRegenerateSummaries(TestCase):
    """End-to-end checks: feed runs in, regenerate, assert summary."""

    def setUp(self):
        self.start1 = datetime(2023, 1, 1, tzinfo=timezone.utc)
        self.end1 = datetime(2023, 5, 1, tzinfo=timezone.utc)
        self.start2 = datetime(2023, 6, 1, tzinfo=timezone.utc)
        self.end2 = datetime(2023, 10, 1, tzinfo=timezone.utc)

    def test_vector_summary_sums_total_net_gain(self):
        """``vector_summary.total_net_gain`` must equal the sum of
        per-run ``total_net_gain`` values — this is the metric the
        notebook 03 ranking table displays."""
        bt = Backtest(
            algorithm_id="alg-1",
            vector_runs=[
                _make_run(self.start1, self.end1, gain=120, trades=4),
                _make_run(self.start2, self.end2, gain=80, trades=3),
            ],
        )

        bt.regenerate_summaries()

        self.assertIsNotNone(bt.vector_summary)
        self.assertEqual(bt.vector_summary.total_net_gain, 200)
        self.assertEqual(bt.vector_summary.number_of_trades, 7)
        self.assertEqual(bt.vector_summary.number_of_trades_closed, 7)

    def test_event_summary_isolated_from_vector_runs(self):
        """The event summary must be derived purely from event runs,
        and vice versa — the engines do not bleed into each other."""
        bt = Backtest(
            algorithm_id="alg-2",
            vector_runs=[
                _make_run(self.start1, self.end1, gain=500, trades=10),
            ],
            event_runs=[
                _make_run(self.start1, self.end1, gain=50, trades=2),
            ],
        )

        bt.regenerate_summaries()

        self.assertEqual(bt.vector_summary.total_net_gain, 500)
        self.assertEqual(bt.event_summary.total_net_gain, 50)
        self.assertEqual(bt.vector_summary.number_of_trades, 10)
        self.assertEqual(bt.event_summary.number_of_trades, 2)

    def test_empty_engine_slot_yields_none_summary(self):
        """An engine with no runs must have its summary slot reset to
        ``None`` (not a stale summary from a prior regeneration)."""
        bt = Backtest(
            algorithm_id="alg-3",
            vector_runs=[
                _make_run(self.start1, self.end1, gain=10, trades=1),
            ],
            event_runs=[],
        )

        bt.regenerate_summaries()

        self.assertIsNotNone(bt.vector_summary)
        self.assertIsNone(bt.event_summary)

    def test_drops_summary_when_runs_cleared(self):
        """Clearing runs and regenerating must clear the summary too —
        guards against the stale-summary bug where pruned runs would
        leave behind their aggregated metrics."""
        bt = Backtest(
            algorithm_id="alg-4",
            vector_runs=[
                _make_run(self.start1, self.end1, gain=10, trades=1),
            ],
        )
        bt.regenerate_summaries()
        self.assertIsNotNone(bt.vector_summary)

        bt.vector_runs = []
        bt.regenerate_summaries()
        self.assertIsNone(bt.vector_summary)

    def test_sharpe_weighted_across_runs(self):
        """Sharpe ratio is a weighted mean across runs (per the
        aggregator contract). Two equal-length runs with Sharpe = 2.0
        and 1.0 must yield an aggregate strictly between them."""
        bt = Backtest(
            algorithm_id="alg-5",
            vector_runs=[
                _make_run(
                    self.start1, self.end1, gain=10, trades=1,
                    days=200, sharpe=2.0,
                ),
                _make_run(
                    self.start2, self.end2, gain=10, trades=1,
                    days=200, sharpe=1.0,
                ),
            ],
        )

        bt.regenerate_summaries()

        self.assertGreater(bt.vector_summary.sharpe_ratio, 1.0)
        self.assertLess(bt.vector_summary.sharpe_ratio, 2.0)
        # Equal-weight runs ⇒ aggregate clusters near the simple mean.
        self.assertAlmostEqual(
            bt.vector_summary.sharpe_ratio, 1.5, places=1
        )

    def test_get_summary_returns_regenerated_value(self):
        """``Backtest.get_summary("vector")`` (the public read path used
        by notebook 03's ranking + filter logic) must reflect the
        regenerated aggregate."""
        bt = Backtest(
            algorithm_id="alg-6",
            vector_runs=[
                _make_run(self.start1, self.end1, gain=30, trades=2),
                _make_run(self.start2, self.end2, gain=70, trades=5),
            ],
        )
        bt.regenerate_summaries()

        summary = bt.get_summary("vector")
        self.assertEqual(summary.total_net_gain, 100)
        self.assertEqual(summary.number_of_trades_closed, 7)
