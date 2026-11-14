from unittest import TestCase
from importlib.util import find_spec

import pandas as pd

from investing_algorithm_framework import (
    PortfolioConfiguration, PositionSize, ScalingRule, SignalSeries,
    SignalSide, TradingCost,
)
from scripts.bench_vector_snapshot_events import CyclingStrategy, workload


class ThreeEntryStrategy(CyclingStrategy):
    def __init__(self, percentage=100 / 3):
        super().__init__(["ASSET0"])
        self.position_sizes = [
            PositionSize(symbol="ASSET0", percentage_of_portfolio=percentage),
        ]
        self.scaling_rules = [
            ScalingRule(symbol="ASSET0", max_entries=3, scale_in_percentage=[100, 100]),
        ]

    def generate_signal_series(self, data):
        index = data["ASSET0/EUR"].index
        for side, offsets in (
            (SignalSide.OPEN_LONG, (0,)),
            (SignalSide.SCALE_IN, (1, 2)),
            (SignalSide.CLOSE_LONG, (3,)),
        ):
            yield SignalSeries(
                symbol="ASSET0", side=side,
                series=pd.Series(
                    [position % 4 in offsets for position in range(len(index))],
                    index=index,
                ),
            )


class ReentryStrategy(CyclingStrategy):
    def __init__(self):
        super().__init__(["ASSET0"])
        self.position_sizes = [
            PositionSize(symbol="ASSET0", percentage_of_portfolio=100),
        ]

    def generate_signal_series(self, data):
        index = data["ASSET0/EUR"].index
        for side, offsets in (
            (SignalSide.OPEN_LONG, (0, 4)),
            (SignalSide.CLOSE_LONG, (2, 6)),
        ):
            yield SignalSeries(
                symbol="ASSET0", side=side,
                series=pd.Series(
                    [position in offsets for position in range(len(index))],
                    index=index,
                ),
            )


class TestVectorCapitalRoundoff(TestCase):
    def run_three_entries(self, balance, percentage=100 / 3):
        service, arguments = workload(8, 1)
        strategy = ThreeEntryStrategy(percentage)
        arguments["strategy"] = strategy
        arguments["portfolio_configuration"] = PortfolioConfiguration(
            market="BITVAVO", trading_symbol="EUR", initial_balance=balance,
            trading_costs=[TradingCost(symbol="ASSET0", fee_percentage=0)],
        )
        return service.run(**arguments)

    def test_equal_thirds_fill_at_small_and_large_capitals(self):
        for balance in (1000, 10000, 100000):
            with self.subTest(balance=balance):
                run = self.run_three_entries(balance)
                self.assertEqual(len(run.trades), 6)
                self.assertTrue(all(event["executed"] for event in run.signal_events))
                self.assertGreaterEqual(
                    min(snapshot.unallocated for snapshot in run.portfolio_snapshots),
                    -balance * 1e-9,
                )

    def test_normalized_equity_is_capital_invariant(self):
        runs = [self.run_three_entries(balance) for balance in (1000, 100000)]
        for low, high in zip(runs[0].portfolio_snapshots, runs[1].portfolio_snapshots):
            self.assertAlmostEqual(low.total_value / 1000, high.total_value / 100000, places=12)

    def test_real_overspend_is_still_rejected(self):
        run = self.run_three_entries(1000, percentage=40)
        self.assertEqual(len(run.trades), 4)
        rejected = [event for event in run.signal_events if not event["executed"]]
        self.assertEqual(len(rejected), 2)
        self.assertTrue(all(event["reason"] == "insufficient_capital" for event in rejected))

    def run_reentry(self, fee=0, exit_price=90, backend="python"):
        service, arguments = workload(8, 1)
        frames = service.data_provider_service.get_vectorized_backtest_data()
        for column in ("Open", "High", "Low", "Close"):
            frames["ASSET0/EUR"][column] = [
                100, 100, exit_price, exit_price, 100, 100, 110, 110,
            ]
            frames["ASSET0/EUR"][column] = frames["ASSET0/EUR"][column].astype(float)
        arguments["strategy"] = ReentryStrategy()
        arguments["portfolio_configuration"] = PortfolioConfiguration(
            market="BITVAVO", trading_symbol="EUR", initial_balance=1000,
            trading_costs=[TradingCost(symbol="ASSET0", fee_percentage=fee)],
        )
        arguments["execution_backend"] = backend
        return service.run(**arguments)

    def test_static_reentry_caps_to_cash_after_losses_and_fees(self):
        for fee in (0, 1):
            with self.subTest(fee=fee):
                run = self.run_reentry(fee=fee)
                self.assertEqual(len(run.trades), 2)
                fraction = fee / 100
                cash_after_loss = 1000 * (1 - fraction) * 0.9 * (1 - fraction)
                self.assertAlmostEqual(
                    run.trades[1].cost, cash_after_loss * (1 - fraction),
                )
                self.assertTrue(all(event["executed"] for event in run.signal_events))
                self.assertGreaterEqual(
                    min(snapshot.unallocated for snapshot in run.portfolio_snapshots),
                    -1e-8,
                )
                self.assertAlmostEqual(
                    run.portfolio_snapshots[1].total_value, 1000 * (1 - fraction),
                )

    def test_last_scale_in_is_cash_capped_after_a_losing_cycle(self):
        service, arguments = workload(8, 1)
        frames = service.data_provider_service.get_vectorized_backtest_data()
        for column in ("Open", "High", "Low", "Close"):
            frames["ASSET0/EUR"][column] = [100., 100., 100., 90., 100., 100., 100., 100.]
        arguments["strategy"] = ThreeEntryStrategy()
        arguments["portfolio_configuration"] = PortfolioConfiguration(
            market="BITVAVO", trading_symbol="EUR", initial_balance=1000,
            trading_costs=[TradingCost(symbol="ASSET0", fee_percentage=0)],
        )
        run = service.run(**arguments)
        self.assertEqual(len(run.trades), 6)
        self.assertAlmostEqual(run.trades[5].cost, 900 - 2 * (1000 / 3))
        self.assertTrue(all(event["executed"] for event in run.signal_events))
        self.assertGreaterEqual(
            min(snapshot.unallocated for snapshot in run.portfolio_snapshots), -1e-8,
        )

    def test_static_winning_reentry_releases_full_reservation_without_compounding(self):
        run = self.run_reentry(fee=1, exit_price=110)
        self.assertEqual(len(run.trades), 2)
        self.assertAlmostEqual(run.trades[1].cost, 990)

    def test_native_reentry_matches_cash_capped_python(self):
        if find_spec("iaf_confluence_native") is None:
            self.skipTest("Optional native extension is not installed")
        for fee in (0, 1):
            with self.subTest(fee=fee):
                python = self.run_reentry(fee=fee)
                native = self.run_reentry(fee=fee, backend="rust")
                self.assertEqual(len(native.trades), 2)
                self.assertAlmostEqual(native.trades[1].cost, python.trades[1].cost)
                for expected, actual in zip(python.portfolio_snapshots, native.portfolio_snapshots):
                    self.assertAlmostEqual(expected.unallocated, actual.unallocated)
                    self.assertAlmostEqual(expected.total_value, actual.total_value)
