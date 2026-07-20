"""Unit tests for the runner-level universe helpers added in Phase 2b.

These cover :func:`_build_strategy_universe_map` and
:func:`_apply_universes` directly (the post-run hook used by
``run_*_backtests(universe=...)``), without spinning up the full
backtest engine.
"""
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase
from unittest.mock import MagicMock

from investing_algorithm_framework import Backtest, Universe
from investing_algorithm_framework.app.app import (
    _apply_universes,
    _build_strategy_universe_map,
)
from investing_algorithm_framework.domain import (
    BacktestDateRange,
    BacktestMetrics,
    BacktestRun,
    BacktestWindow,
    OperationalException,
    PortfolioSnapshot,
)
from investing_algorithm_framework.domain.backtesting import (
    build_strategy_universe_map as _domain_build_strategy_universe_map,
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
    """Lightweight strategy stub with the attributes the helpers read."""
    s = MagicMock()
    s.algorithm_id = algorithm_id
    s.symbols = list(symbols)
    return s


class BuildStrategyUniverseMapTests(TestCase):

    def test_returns_empty_when_no_universes(self):
        self.assertEqual(
            _build_strategy_universe_map(
                [_make_strategy("alg-a", ["BTC", "ETH"])], None,
            ),
            {},
        )

    def test_single_universe_assigns_all(self):
        u = Universe(key="basket", symbols=["BTC", "ETH", "SOL"],
                     trading_symbol="EUR", market="BITVAVO")
        s = _make_strategy("alg-a", ["BTC", "ETH"])
        mapping = _build_strategy_universe_map([s], u)
        self.assertEqual(mapping, {"alg-a": u})

    def test_disjoint_universes_match_by_subset(self):
        u_btc = Universe(key="btc_only", symbols=["BTC"],
                         trading_symbol="EUR", market="BITVAVO")
        u_alts = Universe(key="alts", symbols=["ETH", "SOL", "ADA"],
                          trading_symbol="EUR", market="BITVAVO")
        s_btc = _make_strategy("alg-btc", ["BTC"])
        s_alts = _make_strategy("alg-alts", ["ETH", "SOL"])
        mapping = _domain_build_strategy_universe_map(
            [s_btc, s_alts], [u_btc, u_alts]
        )
        self.assertIs(mapping["alg-btc"], u_btc)
        self.assertIs(mapping["alg-alts"], u_alts)

    def test_overlapping_universes_pick_smallest(self):
        u_small = Universe(key="small", symbols=["BTC", "ETH"],
                           trading_symbol="EUR", market="BITVAVO")
        u_big = Universe(
            key="big", symbols=["BTC", "ETH", "SOL", "ADA", "DOT"],
            trading_symbol="EUR", market="BITVAVO",
        )
        s = _make_strategy("alg-a", ["BTC", "ETH"])
        mapping = _domain_build_strategy_universe_map([s], [u_big, u_small])
        self.assertIs(mapping["alg-a"], u_small)

    def test_no_match_raises(self):
        u = Universe(key="basket", symbols=["BTC", "ETH"],
                     trading_symbol="EUR", market="BITVAVO")
        s = _make_strategy("alg-a", ["BTC", "DOGE"])
        with self.assertRaises(OperationalException):
            _build_strategy_universe_map([s], u)

    def test_strategy_without_symbols_single_universe(self):
        u = Universe(key="basket", symbols=["BTC", "ETH"],
                     trading_symbol="EUR", market="BITVAVO")
        s = _make_strategy("alg-a", [])
        mapping = _build_strategy_universe_map([s], u)
        self.assertIs(mapping["alg-a"], u)

    def test_strategy_without_symbols_multiple_universes_raises(self):
        u1 = Universe(key="a", symbols=["BTC"],
                      trading_symbol="EUR", market="BITVAVO")
        u2 = Universe(key="b", symbols=["ETH"],
                      trading_symbol="EUR", market="BITVAVO")
        s = _make_strategy("alg-a", [])
        with self.assertRaises(OperationalException):
            _domain_build_strategy_universe_map([s], [u1, u2])

    def test_duplicate_keys_raise(self):
        u1 = Universe(key="dup", symbols=["BTC"],
                      trading_symbol="EUR", market="BITVAVO")
        u2 = Universe(key="dup", symbols=["ETH"],
                      trading_symbol="EUR", market="BITVAVO")
        s = _make_strategy("alg-a", ["BTC"])
        with self.assertRaises(OperationalException):
            _domain_build_strategy_universe_map([s], [u1, u2])

    def test_missing_key_raises(self):
        u = Universe(key="", symbols=["BTC"],
                     trading_symbol="EUR", market="BITVAVO")
        s = _make_strategy("alg-a", ["BTC"])
        with self.assertRaises(OperationalException):
            _build_strategy_universe_map([s], u)


class ApplyUniversesTests(TestCase):

    def test_noop_when_no_universes(self):
        bt = _make_backtest("alg-a", ["BTC"])
        _apply_universes([bt], None, [_make_strategy("alg-a", ["BTC"])], None)
        self.assertEqual(bt.universes, [])

    def test_stamps_universe_and_tags_runs(self):
        u = Universe(key="basket", symbols=["BTC", "ETH"],
                     trading_symbol="EUR", market="BITVAVO")
        bt = _make_backtest("alg-a", ["BTC", "ETH"])
        s = _make_strategy("alg-a", ["BTC", "ETH"])
        _apply_universes([bt], u, [s], None)
        self.assertEqual(bt.universes, [u])
        self.assertEqual(
            bt.vector_runs[0].metadata.get("universe_key"), "basket",
        )
        self.assertIn("basket", bt.vector_summaries_by_universe)

    def test_persists_to_disk_when_directory_provided(self, ):
        u = Universe(key="basket", symbols=["BTC", "ETH"],
                     trading_symbol="EUR", market="BITVAVO")
        bt = _make_backtest("alg-a", ["BTC", "ETH"])
        s = _make_strategy("alg-a", ["BTC", "ETH"])

        from investing_algorithm_framework.domain.backtesting.bundle import (
            save_bundle, open_bundle, BUNDLE_EXT,
        )

        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / f"alg-a{BUNDLE_EXT}"
            # Simulate the runner having persisted the bundle first.
            save_bundle(bt, target)

            _apply_universes([bt], u, [s], tmp)

            reloaded = open_bundle(target)
            self.assertEqual(
                [getattr(x, "key", None) for x in (reloaded.universes or [])],
                ["basket"],
            )
            self.assertEqual(
                reloaded.vector_runs[0].metadata.get("universe_key"),
                "basket",
            )

    def test_overwrite_false_preserves_existing_universe_key(self):
        u = Universe(key="basket", symbols=["BTC", "ETH"],
                     trading_symbol="EUR", market="BITVAVO")
        bt = _make_backtest("alg-a", ["BTC", "ETH"])
        bt.vector_runs[0].metadata = {"universe_key": "preexisting"}
        s = _make_strategy("alg-a", ["BTC", "ETH"])
        _apply_universes([bt], u, [s], None)
        self.assertEqual(
            bt.vector_runs[0].metadata.get("universe_key"), "preexisting",
        )

    def test_validation_runs_before_disk_io(self):
        u = Universe(key="basket", symbols=["BTC", "ETH"],
                     trading_symbol="EUR", market="BITVAVO")
        bt = _make_backtest("alg-a", ["BTC", "DOGE"])
        s = _make_strategy("alg-a", ["BTC", "DOGE"])
        with self.assertRaises(OperationalException):
            _apply_universes([bt], u, [s], None)
