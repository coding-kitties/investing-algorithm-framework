from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase
from uuid import uuid4

import pandas as pd

from investing_algorithm_framework import (
    BacktestDateRange,
    BacktestEngine,
    BacktestWindow,
    CooldownRule,
    CSVOHLCVDataProvider,
    DataSource,
    DataType,
    PositionMode,
    PositionSize,
    RESOURCE_DIRECTORY,
    Schedule,
    SignalSeries,
    SignalSide,
    StopLossRule,
    Study,
    TakeProfitRule,
    TimeUnit,
    TradeStatus,
    TradingStrategy,
    Universe,
    create_app,
)


CSV_FILENAME = "OHLCV_BTC-EUR_BITVAVO_2h_LONG_SHORT_CYCLE.csv"
WARMUP = 5
START = datetime(2020, 12, 20, 10, tzinfo=timezone.utc)
END = datetime(2020, 12, 21, 6, tzinfo=timezone.utc)


class HedgeSignalsStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.HOUR)

    def __init__(
        self, signals, *, take_profits=None, stop_losses=None,
        cooldowns=None, position_percentage=40,
    ):
        self._signals = signals
        super().__init__(
            algorithm_id=f"vector_hedge_{uuid4().hex}",
            data_sources=[DataSource(
                symbol="BTC/EUR",
                data_type=DataType.OHLCV,
                time_frame="2h",
                warmup_window=WARMUP,
                market="BITVAVO",
                identifier="BTC_EUR_OHLCV",
                pandas=True,
            )],
            schedule=self.schedule,
            symbols=["BTC"],
            position_sizes=[PositionSize(
                symbol="BTC",
                percentage_of_portfolio=position_percentage,
            )],
            take_profits=take_profits,
            stop_losses=stop_losses,
            cooldowns=cooldowns,
        )

    def generate_signal_series(self, data):
        index = data["BTC_EUR_OHLCV"].index
        for side in SignalSide:
            series = pd.Series(False, index=index)
            for bar_index in self._signals.get(side, ()):
                series.iloc[bar_index + WARMUP] = True
            yield SignalSeries(symbol="BTC", side=side, series=series)


def _run(strategy):
    resources = Path(__file__).parent.parent.parent / "resources"
    csv_path = resources / "test_data" / "ohlcv" / CSV_FILENAME
    app = create_app(
        name=f"VectorHedge{uuid4().hex}",
        config={RESOURCE_DIRECTORY: str(resources)},
    )
    app.add_market(
        market="BITVAVO",
        trading_symbol="EUR",
        initial_balance=1000,
        position_mode=PositionMode.HEDGE,
    )
    app.add_data_provider(
        data_provider=CSVOHLCVDataProvider(
            storage_path=str(csv_path),
            symbol="BTC/EUR",
            time_frame="2h",
            market="BITVAVO",
            warmup_window=WARMUP,
        ),
        priority=1,
    )
    study = Study(
        universe=Universe(market="BITVAVO", trading_symbol="EUR"),
        backtest_windows=[BacktestWindow(train_range=BacktestDateRange(
            start_date=START, end_date=END,
        ))],
        engines=[BacktestEngine.VECTOR],
    )
    backtests = app.run_backtest(
        strategy=strategy, study=study, use_checkpoints=False,
    )
    return backtests[0].get_all_backtest_runs()[0]


def _both_open_signals(extra=None):
    return {
        SignalSide.OPEN_LONG: [0],
        SignalSide.OPEN_SHORT: [0],
        **(extra or {}),
    }


class TestVectorHedgeMode(TestCase):
    def test_simultaneous_long_and_short_are_exposed_in_output(self):
        run = _run(HedgeSignalsStrategy(_both_open_signals()))

        self.assertEqual(2, len(run.trades))
        self.assertEqual(2, run.number_of_trades_open)
        position = run.positions[0]
        self.assertGreater(position.long_amount, 0)
        self.assertGreater(position.short_amount, 0)
        self.assertAlmostEqual(
            position.amount,
            position.long_amount - position.short_amount,
        )
        snapshot = run.portfolio_snapshots[-1].position_snapshots[0]
        self.assertEqual(position.long_amount, snapshot.long_amount)
        self.assertEqual(position.short_amount, snapshot.short_amount)
        self.assertEqual(position.long_cost, snapshot.long_cost)
        self.assertEqual(position.short_cost, snapshot.short_cost)
        payload = run.to_dict()
        serialized = payload["portfolio_snapshots"][-1][
            "position_snapshots"
        ][0]
        self.assertIn("long_amount", serialized)
        self.assertIn("short_amount", serialized)

    def test_closes_are_independent_and_pnl_is_side_specific(self):
        run = _run(HedgeSignalsStrategy(_both_open_signals({
            SignalSide.CLOSE_LONG: [3],
            SignalSide.CLOSE_SHORT: [4],
        })))

        long_trade = next(trade for trade in run.trades if not trade.is_short)
        short_trade = next(trade for trade in run.trades if trade.is_short)
        self.assertLess(long_trade.closed_at, short_trade.closed_at)
        self.assertTrue(TradeStatus.CLOSED.equals(long_trade.status))
        self.assertTrue(TradeStatus.CLOSED.equals(short_trade.status))
        long_close = next(
            order for order in long_trade.orders
            if order.order_side == "SELL"
        )
        short_close = next(
            order for order in short_trade.orders
            if order.order_side == "BUY"
        )
        self.assertAlmostEqual(
            long_trade.net_gain,
            (long_close.price - long_trade.open_price) * long_close.amount,
        )
        self.assertAlmostEqual(
            short_trade.net_gain,
            (short_trade.open_price - short_close.price) * short_close.amount,
        )
        self.assertLess(long_trade.net_gain, 0)
        self.assertGreater(short_trade.net_gain, 0)

    def test_take_profit_evaluates_each_leg_independently(self):
        run = _run(HedgeSignalsStrategy(
            _both_open_signals(),
            take_profits=[
                TakeProfitRule(8, 100, "BTC", side="long"),
                TakeProfitRule(10, 100, "BTC", side="short"),
            ],
        ))

        long_trade = next(trade for trade in run.trades if not trade.is_short)
        short_trade = next(trade for trade in run.trades if trade.is_short)
        self.assertLess(short_trade.closed_at, long_trade.closed_at)
        events = [
            event for event in run.signal_events
            if event["signal"] == "take_profit" and event["executed"]
        ]
        self.assertEqual(2, len(events))

    def test_stop_loss_evaluates_each_leg_independently(self):
        run = _run(HedgeSignalsStrategy(
            _both_open_signals(),
            stop_losses=[
                StopLossRule(10, 100, "BTC", side="long"),
                StopLossRule(8, 100, "BTC", side="short"),
            ],
        ))

        long_trade = next(trade for trade in run.trades if not trade.is_short)
        short_trade = next(trade for trade in run.trades if trade.is_short)
        self.assertLess(long_trade.closed_at, short_trade.closed_at)
        events = [
            event for event in run.signal_events
            if event["signal"] == "stop_loss" and event["executed"]
        ]
        self.assertEqual(2, len(events))

    def test_cooldown_blocks_only_the_triggering_leg(self):
        run = _run(HedgeSignalsStrategy(
            _both_open_signals({
                SignalSide.CLOSE_LONG: [1],
                SignalSide.CLOSE_SHORT: [1],
            }),
            cooldowns=[CooldownRule(
                symbol="BTC", trigger="buy", blocks="any", bars=3,
            )],
        ))

        long_trade = next(trade for trade in run.trades if not trade.is_short)
        short_trade = next(trade for trade in run.trades if trade.is_short)
        self.assertTrue(TradeStatus.OPEN.equals(long_trade.status))
        self.assertTrue(TradeStatus.CLOSED.equals(short_trade.status))
        sell_event = next(
            event for event in run.signal_events
            if event["signal"] == "sell"
        )
        cover_event = next(
            event for event in run.signal_events
            if event["signal"] == "cover"
        )
        self.assertEqual("in_cooldown_rule", sell_event["reason"])
        self.assertFalse(sell_event["executed"])
        self.assertTrue(cover_event["executed"])

    def test_same_bar_capital_is_consumed_in_long_then_short_order(self):
        run = _run(HedgeSignalsStrategy(
            _both_open_signals(), position_percentage=60,
        ))

        self.assertEqual(1, len(run.trades))
        self.assertFalse(run.trades[0].is_short)
        short_event = next(
            event for event in run.signal_events
            if event["signal"] == "short"
        )
        self.assertFalse(short_event["executed"])
        self.assertEqual("insufficient_capital", short_event["reason"])