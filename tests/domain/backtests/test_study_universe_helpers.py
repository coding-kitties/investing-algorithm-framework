"""Unit tests for the domain-level study/universe stamp helpers
introduced in Phase 2b.

These cover :func:`build_strategy_universe_map`, :func:`stamp_backtest`
and :func:`stamp_backtests` directly, without spinning up the full
backtest engine. They guarantee the helpers can be called in-process
by the runner before checkpoint flushes.
"""
from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import MagicMock

from investing_algorithm_framework import Backtest, Universe
from investing_algorithm_framework.domain import BacktestWindow, BacktestDateRange
from investing_algorithm_framework.domain import (
    BacktestMetrics,
    BacktestRun,
    OperationalException,
    PortfolioSnapshot,
    build_strategy_universe_map,
    stamp_backtest,
    stamp_backtests,
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
            created_at="2023-05-01 00:00:00",
            total_value=1100,
            trading_symbol="EUR",
            unallocated=100,
        ),
    ]


def _make_run(symbols, metadata=None):
    start = datetime(2023, 1, 1, tzinfo=timezone.utc)
    end = datetime(2023, 5, 1, tzinfo=timezone.utc)
    return BacktestRun(
        backtest_window=BacktestWindow(
            train_range=BacktestDateRange(
                start_date=start,
                end_date=end,
                name="2023Q1",
            )
        ),
        created_at=datetime.now(tz=timezone.utc),
        orders=[],
        trades=[],
        positions=[],
        portfolio_snapshots=_snapshots(),
        trading_symbol="EUR",
        symbols=list(symbols),
        data_sources=[],
        number_of_runs=1,
        initial_unallocated=1000,
        metadata=dict(metadata or {}),
        backtest_metrics=BacktestMetrics(
            backtest_start_date=start.replace(tzinfo=None),

            backtest_end_date=end.replace(tzinfo=None),
            total_net_gain=100,
            total_net_gain_percentage=0.1,
            number_of_trades=2,
            number_of_trades_closed=2,
            win_rate=0.5,
            gross_profit=100,
            gross_loss=0,
            total_number_of_days=120,
        ),
    )


def _make_backtest(algorithm_id, symbols):
    bt = Backtest(algorithm_id=algorithm_id)
    bt.vector_runs = [_make_run(symbols)]
    return bt


def _make_strategy(algorithm_id, symbols):
    s = MagicMock()
    s.algorithm_id = algorithm_id
    s.symbols = list(symbols)
    return s


class BuildStrategyUniverseMapTests(TestCase):

    def test_returns_empty_when_no_universes(self):
        self.assertEqual(
            build_strategy_universe_map(
                [_make_strategy("alg-a", ["BTC"])], None
            ),
            {},
        )
        self.assertEqual(
            build_strategy_universe_map(
                [_make_strategy("alg-a", ["BTC"])], []
            ),
            {},
        )

    def test_subset_match(self):
        u = Universe(key="basket", symbols=["BTC", "ETH", "SOL"],
                     trading_symbol="EUR", market="BITVAVO")
        s = _make_strategy("alg-a", ["BTC", "ETH"])
        self.assertEqual(
            build_strategy_universe_map([s], [u]),
            {"alg-a": u},
        )

    def test_no_match_raises(self):
        u = Universe(key="basket", symbols=["BTC", "ETH"],
                     trading_symbol="EUR", market="BITVAVO")
        s = _make_strategy("alg-a", ["BTC", "DOGE"])
        with self.assertRaises(OperationalException):
            build_strategy_universe_map([s], [u])

    def test_overlapping_picks_smallest(self):
        u_small = Universe(key="small", symbols=["BTC", "ETH"],
                           trading_symbol="EUR", market="BITVAVO")
        u_big = Universe(
            key="big", symbols=["BTC", "ETH", "SOL", "ADA"],
            trading_symbol="EUR", market="BITVAVO",
        )
        s = _make_strategy("alg-a", ["BTC", "ETH"])
        self.assertIs(
            build_strategy_universe_map([s], [u_big, u_small])["alg-a"],
            u_small,
        )

    def test_duplicate_keys_raise(self):
        u1 = Universe(key="dup", symbols=["BTC"],
                      trading_symbol="EUR", market="BITVAVO")
        u2 = Universe(key="dup", symbols=["ETH"],
                      trading_symbol="EUR", market="BITVAVO")
        with self.assertRaises(OperationalException):
            build_strategy_universe_map(
                [_make_strategy("alg-a", ["BTC"])], [u1, u2]
            )

    def test_missing_key_raises(self):
        u = Universe(key="", symbols=["BTC"],
                     trading_symbol="EUR", market="BITVAVO")
        with self.assertRaises(OperationalException):
            build_strategy_universe_map(
                [_make_strategy("alg-a", ["BTC"])], [u]
            )

    def test_strategy_without_symbols_single_universe(self):
        u = Universe(key="basket", symbols=["BTC", "ETH"],
                     trading_symbol="EUR", market="BITVAVO")
        s = _make_strategy("alg-a", [])
        self.assertIs(
            build_strategy_universe_map([s], [u])["alg-a"], u,
        )

    def test_strategy_without_symbols_multi_raises(self):
        u1 = Universe(key="a", symbols=["BTC"],
                      trading_symbol="EUR", market="BITVAVO")
        u2 = Universe(key="b", symbols=["ETH"],
                      trading_symbol="EUR", market="BITVAVO")
        with self.assertRaises(OperationalException):
            build_strategy_universe_map(
                [_make_strategy("alg-a", [])], [u1, u2]
            )


class StampBacktestTests(TestCase):

    def test_noop_when_all_none(self):
        bt = _make_backtest("alg-a", ["BTC"])
        stamp_backtest(bt)
        self.assertEqual(bt.get_study().name, "default")
        self.assertEqual(bt.universes, [])
        self.assertNotIn(
            "universe_key",
            (bt.vector_runs[0].metadata or {}),
        )

    def test_stamps_study_fields(self):
        bt = _make_backtest("alg-a", ["BTC"])
        stamp_backtest(
            bt,
            study_name="in_sample",
            study_description="rolling 6m sweep",
        )
        self.assertEqual(bt.get_study().name, "in_sample")
        self.assertEqual(bt.get_study().description, "rolling 6m sweep")

    def test_stamps_universe_and_tags_runs(self):
        u = Universe(key="basket", symbols=["BTC", "ETH"],
                     trading_symbol="EUR", market="BITVAVO")
        bt = _make_backtest("alg-a", ["BTC", "ETH"])
        stamp_backtest(bt, universe=u)
        self.assertEqual(bt.universes, [u])
        self.assertEqual(
            bt.vector_runs[0].metadata.get("universe_key"), "basket",
        )
        self.assertIn("basket", bt.vector_summaries_by_universe)

    def test_does_not_overwrite_existing_universe_key(self):
        u = Universe(key="basket", symbols=["BTC"],
                     trading_symbol="EUR", market="BITVAVO")
        bt = _make_backtest("alg-a", ["BTC"])
        bt.vector_runs[0].metadata["universe_key"] = "preset"
        stamp_backtest(bt, universe=u)
        self.assertEqual(
            bt.vector_runs[0].metadata["universe_key"], "preset",
        )


class StampBacktestsTests(TestCase):

    def test_applies_to_each_via_universe_map(self):
        u_a = Universe(key="a", symbols=["BTC"],
                       trading_symbol="EUR", market="BITVAVO")
        u_b = Universe(key="b", symbols=["ETH"],
                       trading_symbol="EUR", market="BITVAVO")
        bt_a = _make_backtest("alg-a", ["BTC"])
        bt_b = _make_backtest("alg-b", ["ETH"])
        stamp_backtests(
            [bt_a, bt_b],
            study_name="oos",
            universe_map={"alg-a": u_a, "alg-b": u_b},
        )
        self.assertEqual(bt_a.get_study().name, "oos")
        self.assertEqual(bt_a.universes, [u_a])
        self.assertEqual(bt_b.universes, [u_b])

    def test_unmapped_id_only_gets_study_fields(self):
        u_a = Universe(key="a", symbols=["BTC"],
                       trading_symbol="EUR", market="BITVAVO")
        bt_a = _make_backtest("alg-a", ["BTC"])
        bt_b = _make_backtest("alg-b", ["ETH"])
        stamp_backtests(
            [bt_a, bt_b],
            study_name="oos",
            universe_map={"alg-a": u_a},
        )
        self.assertEqual(bt_b.get_study().name, "oos")
        self.assertEqual(bt_b.universes, [])

    def test_full_noop(self):
        bt = _make_backtest("alg-a", ["BTC"])
        stamp_backtests([bt])
        self.assertEqual(bt.get_study().name, "default")
        self.assertEqual(bt.universes, [])
