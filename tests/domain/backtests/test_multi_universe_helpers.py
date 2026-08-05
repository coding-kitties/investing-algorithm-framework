"""Tests for the multi-universe Backtest helpers added in Phase 2a.

Covers the additive surface that lets callers compose a v4
multi-universe envelope without going through the (deferred)
``run_backtests(universes=...)`` runner overload:

* :meth:`Backtest.tag_runs_universe` stamps ``run.metadata["universe_key"]``
  on every run, optionally honouring an ``overwrite=False`` guard.
* :meth:`Backtest.regenerate_summaries_by_universe` groups runs by their
  ``universe_key`` tag and rebuilds per-engine
  ``vector_summaries_by_universe`` / ``event_summaries_by_universe``.
* :func:`combine_multi_universe_backtest` merges per-universe Backtest
  bundles (same ``algorithm_id``) into a single v4 envelope with the
  universes catalogue populated, runs tagged, and per-universe
  summaries computed.
"""
from datetime import datetime, timezone
from unittest import TestCase
from investing_algorithm_framework.domain import BacktestWindow, BacktestDateRange

from investing_algorithm_framework import (
    Backtest,
    Universe,
    combine_multi_universe_backtest,
)
from investing_algorithm_framework.domain import (
    BacktestRun,
    BacktestMetrics,
    PortfolioSnapshot,
)


def _snapshots():
    return [
        PortfolioSnapshot(
            created_at="2023-08-07 07:00:00",
            total_value=1000,
            trading_symbol="EUR",
            unallocated=1000,
        ),
        PortfolioSnapshot(
            created_at="2023-12-02 00:00:00",
            total_value=1100,
            trading_symbol="EUR",
            unallocated=100,
        ),
    ]


def _make_run(start, end, *, gain, trades, symbols=None, market=None,
              metadata=None):
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
        data_sources=[{"market": market}] if market else [],
        number_of_runs=10,
        initial_unallocated=1000,
        metadata=dict(metadata or {}),
        backtest_metrics=BacktestMetrics(
            backtest_window=window,
            total_net_gain=gain,
            total_net_gain_percentage=gain / 1000.0,
            number_of_trades=trades,
            number_of_trades_closed=trades,
            win_rate=0.6,
            gross_profit=max(gain, 0),
            gross_loss=abs(min(gain, 0)),
            total_number_of_days=120,
        ),
    )


def _make_backtest(algorithm_id, universe_key, *, gain, symbols, market):
    """Build a single-universe Backtest with one event run."""
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end = datetime(2023, 5, 1, tzinfo=timezone.utc)
    run = _make_run(
        start, end, gain=gain, trades=5,
        symbols=symbols, market=market,
        metadata={"universe_key": universe_key} if universe_key else None,
    )
    return Backtest(
        algorithm_id=algorithm_id,
        event_runs=[run],
        risk_free_rate=0.02,
        universes=[
            Universe(
                key=universe_key or "default",
                symbols=list(symbols),
                trading_symbol="EUR",
                market=market,
            )
        ],
    )


class TestTagRunsUniverse(TestCase):
    def test_stamps_all_runs_both_engines(self):
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 2, 1, tzinfo=timezone.utc)
        bt = Backtest(
            algorithm_id="alg-1",
            event_runs=[_make_run(start, end, gain=10, trades=1)],
            vector_runs=[_make_run(start, end, gain=20, trades=2)],
        )
        bt.tag_runs_universe("majors")
        for engine in ("vector", "event"):
            for run in bt.get_runs(engine):
                self.assertEqual(run.metadata["universe_key"], "majors")

    def test_overwrite_false_preserves_existing_tag(self):
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 2, 1, tzinfo=timezone.utc)
        run_pre_tagged = _make_run(
            start, end, gain=10, trades=1,
            metadata={"universe_key": "alts"},
        )
        run_unset = _make_run(start, end, gain=5, trades=1)
        bt = Backtest(
            algorithm_id="alg-1",
            event_runs=[run_pre_tagged, run_unset],
        )
        bt.tag_runs_universe("majors", overwrite=False)
        self.assertEqual(
            run_pre_tagged.metadata["universe_key"], "alts"
        )
        self.assertEqual(
            run_unset.metadata["universe_key"], "majors"
        )

    def test_engines_filter(self):
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 2, 1, tzinfo=timezone.utc)
        bt = Backtest(
            algorithm_id="alg-1",
            vector_runs=[_make_run(start, end, gain=20, trades=2)],
            event_runs=[_make_run(start, end, gain=10, trades=1)],
        )
        bt.tag_runs_universe("majors", engines=["vector"])
        self.assertEqual(
            bt.get_runs("vector")[0].metadata.get("universe_key"),
            "majors",
        )
        # event run untouched
        self.assertNotIn(
            "universe_key",
            bt.get_runs("event")[0].metadata or {},
        )


class TestRegenerateSummariesByUniverse(TestCase):
    def test_groups_runs_by_universe_key(self):
        start1 = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end1 = datetime(2023, 2, 1, tzinfo=timezone.utc)
        start2 = datetime(2023, 3, 1, tzinfo=timezone.utc)
        end2 = datetime(2023, 4, 1, tzinfo=timezone.utc)
        bt = Backtest(
            algorithm_id="alg-1",
            event_runs=[
                _make_run(
                    start1, end1, gain=100, trades=4,
                    metadata={"universe_key": "majors"},
                ),
                _make_run(
                    start2, end2, gain=50, trades=2,
                    metadata={"universe_key": "majors"},
                ),
                _make_run(
                    start1, end1, gain=-20, trades=3,
                    metadata={"universe_key": "alts"},
                ),
            ],
        )
        bt.regenerate_summaries_by_universe()
        self.assertEqual(
            set(bt.event_summaries_by_universe.keys()),
            {"majors", "alts"},
        )
        self.assertEqual(bt.vector_summaries_by_universe, {})

    def test_skips_runs_without_universe_key(self):
        start = datetime(2023, 1, 1, tzinfo=timezone.utc)
        end = datetime(2023, 2, 1, tzinfo=timezone.utc)
        bt = Backtest(
            algorithm_id="alg-1",
            event_runs=[
                _make_run(start, end, gain=10, trades=1),
                _make_run(
                    start, end, gain=20, trades=2,
                    metadata={"universe_key": "majors"},
                ),
            ],
        )
        bt.regenerate_summaries_by_universe()
        self.assertEqual(
            set(bt.event_summaries_by_universe.keys()), {"majors"}
        )


class TestCombineMultiUniverseBacktest(TestCase):
    def test_merges_per_universe_bundles(self):
        bt_majors = _make_backtest(
            "alg-shared", universe_key=None,
            gain=200, symbols=["BTC", "ETH"], market="BITVAVO",
        )
        bt_alts = _make_backtest(
            "alg-shared", universe_key=None,
            gain=-50, symbols=["XRP", "DOGE"], market="BITVAVO",
        )

        merged = combine_multi_universe_backtest(
            {"majors": bt_majors, "alts": bt_alts},
            study_name="universe-sweep",
            study_description="majors vs alts",
        )

        self.assertEqual(merged.algorithm_id, "alg-shared")
        self.assertEqual(merged.get_study().name, "universe-sweep")
        self.assertEqual(merged.get_study().description, "majors vs alts")
        self.assertEqual(
            sorted(u.key for u in merged.universes), ["alts", "majors"]
        )
        # Every event run is tagged with its universe key.
        tags = {r.metadata["universe_key"] for r in merged.get_runs("event")}
        self.assertEqual(tags, {"majors", "alts"})
        # Per-universe summaries cover both universes; vector slot empty.
        self.assertEqual(
            set(merged.event_summaries_by_universe.keys()),
            {"majors", "alts"},
        )
        self.assertEqual(merged.vector_summaries_by_universe, {})
        # Pooled cross-universe summary is also populated.
        self.assertIsNotNone(merged.event_summary)

    def test_uses_explicit_universes_catalogue(self):
        bt_a = _make_backtest(
            "alg-a", universe_key=None,
            gain=10, symbols=["BTC"], market="BITVAVO",
        )
        bt_b = _make_backtest(
            "alg-a", universe_key=None,
            gain=20, symbols=["ETH"], market="BITVAVO",
        )
        universes = [
            Universe(key="majors", symbols=["BTC"], trading_symbol="EUR"),
            Universe(key="alts", symbols=["ETH"], trading_symbol="EUR"),
        ]
        merged = combine_multi_universe_backtest(
            {"majors": bt_a, "alts": bt_b},
            universes=universes,
        )
        self.assertEqual(
            [u.key for u in merged.universes], ["majors", "alts"]
        )

    def test_raises_on_empty_input(self):
        with self.assertRaises(ValueError):
            combine_multi_universe_backtest({})
