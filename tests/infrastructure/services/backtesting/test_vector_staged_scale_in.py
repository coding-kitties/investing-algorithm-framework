"""Staged cards are raw masks; only accepted fills advance their cursor."""
from unittest import TestCase
from unittest.mock import patch

import pandas as pd

from investing_algorithm_framework import (
    PortfolioConfiguration, PositionSize, ScalingRule, SignalSeries,
    SignalSide, TradingCost,
)
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_backtest_service import VectorBacktestService
from investing_algorithm_framework.infrastructure.services.backtesting \
    .vector_native import NativeExecutionUnsupported
from scripts.bench_vector_snapshot_events import CyclingStrategy, workload


class StagedStrategy(CyclingStrategy):
    def __init__(
        self, symbols, stages, *, entries=(0,), exits=(), trims=(),
        lower=False, cooldown=0, percentage=10, trim_percentage=100,
    ):
        super().__init__(symbols)
        self.stages = stages
        self.entries = entries
        self.exits = exits
        self.trims = trims
        self.lower = lower
        self.position_sizes = [
            PositionSize(symbol=symbol, percentage_of_portfolio=percentage)
            for symbol in symbols
        ]
        self.scaling_rules = [
            ScalingRule(
                symbol=symbol, max_entries=10,
                cooldown_in_bars=cooldown,
                scale_out_percentage=trim_percentage,
            )
            for symbol in symbols
        ]

    def generate_signal_series(self, data):
        for symbol in self.symbols:
            index = data[f"{symbol}/EUR"].index

            def mask(offsets):
                return pd.Series(
                    [i in offsets for i in range(len(index))], index=index
                )

            for side, offsets in (
                (SignalSide.OPEN_LONG, self.entries),
                (SignalSide.CLOSE_LONG, self.exits),
                (SignalSide.SCALE_OUT, self.trims),
            ):
                yield SignalSeries(symbol, side, mask(offsets))
            for stage, offsets in self.stages[symbol].items():
                yield SignalSeries(
                    symbol, SignalSide.SCALE_IN, mask(offsets),
                    metadata={
                        "scale_in_stage": stage,
                        "require_lower_price": self.lower,
                    },
                )


class UnstagedStrategy(StagedStrategy):
    def generate_signal_series(self, data):
        for series in super().generate_signal_series(data):
            yield SignalSeries(series.symbol, series.side, series.series)


class BuyFallbackStrategy(StagedStrategy):
    def generate_signal_series(self, data):
        for series in super().generate_signal_series(data):
            if series.side != SignalSide.SCALE_IN:
                yield series


class TestVectorStagedScaleIn(TestCase):
    def execute(
        self, stages, *, prices=None, bars=10, backend="python",
        hedge=False, deposits=(), dynamic=False, cost=None, **kwargs,
    ):
        service, arguments = workload(bars, len(stages))
        symbols = list(stages)
        frames = service.data_provider_service.get_vectorized_backtest_data()
        for symbol in symbols:
            for column in ("Open", "High", "Low", "Close"):
                frames[f"{symbol}/EUR"][column] = (
                    prices[symbol] if isinstance(prices, dict)
                    else prices if prices is not None else [100.] * bars
                )
        strategy_class = kwargs.pop("strategy_class", StagedStrategy)
        arguments["strategy"] = strategy_class(symbols, stages, **kwargs)
        arguments["portfolio_configuration"] = PortfolioConfiguration(
            market="BITVAVO", trading_symbol="EUR", initial_balance=10000,
            position_mode="hedge" if hedge else "netting",
            trading_costs=[
                cost if cost is not None else
                TradingCost(symbol=symbol, fee_percentage=0)
                for symbol in symbols
            ],
        )
        arguments["execution_backend"] = backend
        arguments["dynamic_position_sizing"] = dynamic
        index = frames[f"{symbols[0]}/EUR"].index
        schedule = [
            (index[i].to_pydatetime(), amount) for i, amount in deposits
        ]
        with patch.object(
            service, "_resolve_deposit_schedule", return_value=schedule,
        ):
            return service.run(**arguments)

    def fills(self, run, symbol="ASSET0"):
        start = pd.Timestamp("2025-01-01", tz="UTC")
        return [
            int((pd.Timestamp(trade.opened_at) - start).total_seconds() / 3600)
            for trade in run.trades if trade.target_symbol == symbol
        ]

    def test_raw_entry_does_not_bypass_separate_stage_masks(self):
        for hedge in (False, True):
            with self.subTest(hedge=hedge):
                run = self.execute(
                    {"ASSET0": {0: (3,), 1: (5,)}},
                    entries=range(10), hedge=hedge,
                )
                self.assertEqual(self.fills(run), [0, 3, 5])

    def test_gap_crossing_fills_only_one_add_per_bar_and_exhausts(self):
        for hedge in (False, True):
            with self.subTest(hedge=hedge):
                run = self.execute(
                    {"ASSET0": {1: range(10), 0: range(10)}},
                    entries=range(10), hedge=hedge,
                )
                self.assertEqual(self.fills(run), [0, 1, 2])

    def test_missing_next_stage_is_exhausted_not_skipped(self):
        run = self.execute(
            {"ASSET0": {0: range(10), 2: range(10)}}, entries=range(10),
        )
        self.assertEqual(self.fills(run), [0, 1])

    def test_cooldown_delays_without_consuming_a_stage(self):
        for hedge in (False, True):
            with self.subTest(hedge=hedge):
                run = self.execute(
                    {"ASSET0": {0: range(1, 10), 1: range(1, 10)}},
                    cooldown=3, hedge=hedge,
                )
                self.assertEqual(self.fills(run), [0, 3, 6])
                self.assertTrue(any(
                    event["signal"] == "scale_in"
                    and event["reason"] == "in_cooldown"
                    for event in run.signal_events
                ))

    def test_capital_denial_retries_same_stage_when_cash_arrives(self):
        run = self.execute(
            {"ASSET0": {0: range(1, 10), 1: range(1, 10)}},
            percentage=100, dynamic=True, deposits=((3, 1000), (5, 1000)),
        )
        self.assertEqual(self.fills(run), [0, 3, 5])
        self.assertTrue(any(
            event["signal"] == "scale_in"
            and event["reason"] == "insufficient_capital"
            for event in run.signal_events
        ))

    def test_failed_open_does_not_advance_or_start_cooldown(self):
        cost = TradingCost(symbol="ASSET0", fee_percentage=0)
        with patch.object(cost, "get_fee", side_effect=[0, 1000, 0, 0]):
            run = self.execute(
                {"ASSET0": {0: (1, 2), 1: (1, 2, 3)}}, cost=cost,
            )
        self.assertEqual(self.fills(run), [0, 2, 3])
        denied = [
            event for event in run.signal_events
            if event["signal"] == "scale_in" and not event["executed"]
        ]
        self.assertEqual(len(denied), 1)
        self.assertEqual(denied[0]["reason"], "insufficient_capital")

    def test_partial_exit_does_not_rearm_and_guard_uses_latest_fill(self):
        for hedge in (False, True):
            with self.subTest(hedge=hedge):
                run = self.execute(
                    {"ASSET0": {0: range(1, 10), 1: range(2, 10)}},
                    trims=(2,), lower=True, hedge=hedge,
                    prices=[100., 90., 90., 95., 85., 85., 85., 85., 85., 85.],
                )
                # The 90 fill was closed by the trim; 95 must still not add.
                self.assertEqual(self.fills(run), [0, 1, 4])

    def test_full_exit_resets_stage_cursor(self):
        for hedge in (False, True):
            with self.subTest(hedge=hedge):
                run = self.execute(
                    {"ASSET0": {0: range(10), 1: range(10)}},
                    entries=(0, 5), exits=(4,), hedge=hedge,
                )
                self.assertEqual(self.fills(run), [0, 1, 2, 5, 6, 7])

    def test_scale_out_to_flat_resets_and_prevents_same_bar_reentry(self):
        run = self.execute(
            {"ASSET0": {0: range(10)}},
            entries=range(10), trims=(1,),
        )
        self.assertEqual(self.fills(run), [0, 2, 3])

    def test_exit_has_priority_over_staged_addition(self):
        run = self.execute(
            {"ASSET0": {0: range(10)}},
            entries=range(10), exits=(1,),
        )
        self.assertEqual(self.fills(run), [0, 2, 3])

    def test_lower_price_is_strict_and_uses_actual_fill(self):
        cost = TradingCost(
            symbol="ASSET0", fee_percentage=0, slippage_percentage=1,
        )
        run = self.execute(
            {"ASSET0": {0: range(1, 10), 1: range(1, 10)}},
            lower=True, cost=cost,
            prices=[
                100., 101., 102., 100.5, 101.505,
                102., 99., 99., 99., 99.,
            ],
        )
        self.assertEqual(self.fills(run), [0, 3, 6])
        self.assertAlmostEqual(run.trades[1].open_price, 101.505)

    def test_symbols_progress_independently(self):
        run = self.execute({
            "ASSET0": {0: (1,), 1: (4,)},
            "ASSET1": {0: (3,), 1: (5,)},
        })
        self.assertEqual(self.fills(run, "ASSET0"), [0, 1, 4])
        self.assertEqual(self.fills(run, "ASSET1"), [0, 3, 5])

    def test_legacy_unstaged_and_buy_fallback_execution_unchanged(self):
        for hedge in (False, True):
            with self.subTest(hedge=hedge):
                unstaged = self.execute(
                    {"ASSET0": {0: (2,), 1: (4,)}}, hedge=hedge,
                    strategy_class=UnstagedStrategy,
                )
                self.assertEqual(self.fills(unstaged), [0, 4])
                fallback = self.execute(
                    {"ASSET0": {}}, hedge=hedge, entries=range(10),
                    strategy_class=BuyFallbackStrategy,
                )
                self.assertEqual(self.fills(fallback), list(range(10)))

    def test_auto_logs_python_fallback_and_rust_rejects_metadata(self):
        with self.assertLogs(
            "investing_algorithm_framework.infrastructure.services."
            "backtesting.vector_backtest_service", level="INFO",
        ) as logs:
            run = self.execute({"ASSET0": {0: (1,)}}, backend="auto")
        self.assertEqual(self.fills(run), [0, 1])
        self.assertIn("Staged SCALE_IN metadata", " ".join(logs.output))
        with self.assertRaisesRegex(
            NativeExecutionUnsupported, "Staged SCALE_IN metadata",
        ):
            self.execute({"ASSET0": {0: (1,)}}, backend="rust")


class TestStagedSignalValidation(TestCase):
    def series(self, stage=None, staged=True):
        return SignalSeries(
            "ASSET0", SignalSide.SCALE_IN,
            pd.Series([True], index=pd.date_range("2025-01-01", periods=1)),
            metadata={"scale_in_stage": stage} if staged else {},
        )

    def test_invalid_stage_types(self):
        for stage in (-1, 0.0, 1.5, True, False, "0", None):
            with self.subTest(stage=stage):
                with self.assertRaisesRegex(ValueError, "nonnegative integer"):
                    VectorBacktestService._bucket_signal_series([
                        self.series(stage),
                    ])

    def test_duplicate_stages(self):
        with self.assertRaisesRegex(ValueError, "Duplicate scale_in_stage"):
            VectorBacktestService._bucket_signal_series([
                self.series(0), self.series(0),
            ])

    def test_mixed_modes_rejected_in_either_order(self):
        for stream in (
            [self.series(0), self.series(staged=False)],
            [self.series(staged=False), self.series(0)],
        ):
            with self.assertRaisesRegex(
                ValueError, "Mixed staged and unstaged",
            ):
                VectorBacktestService._bucket_signal_series(stream)

    def test_unstaged_last_series_still_wins(self):
        first, second = self.series(staged=False), self.series(staged=False)
        _, _, scale_in, _, _, _ = VectorBacktestService._bucket_signal_series(
            [first, second],
        )
        self.assertIs(scale_in["ASSET0"], second.series)
