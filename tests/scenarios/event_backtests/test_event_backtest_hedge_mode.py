from datetime import datetime, timedelta, timezone
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
    SignalSide,
    StopLossRule,
    Study,
    TakeProfitRule,
    TimeUnit,
    TradeStatus,
    TradingStrategy,
    Universe,
    create_app,
    signals_from_column,
)


CSV_FILENAME = "OHLCV_BTC-EUR_BITVAVO_2h_LONG_SHORT_CYCLE.csv"
WARMUP = 5
START = datetime(2020, 12, 20, 10, tzinfo=timezone.utc)
END = datetime(2020, 12, 21, 6, tzinfo=timezone.utc)


class HedgeSignalsStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.HOUR)

    def __init__(
        self, signals, *, take_profits=None, stop_losses=None,
        cooldowns=None,
    ):
        self._signals = signals
        super().__init__(
            algorithm_id=f"event_hedge_{uuid4().hex}",
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
                symbol="BTC", percentage_of_portfolio=40,
            )],
            take_profits=take_profits,
            stop_losses=stop_losses,
            cooldowns=cooldowns,
        )

    def generate_signals(self, context, data):
        frame = data["BTC_EUR_OHLCV"].copy()
        for side in SignalSide:
            column = side.value
            series = pd.Series(False, index=frame.index)
            for bar_index in self._signals.get(side, ()):
                signal_at = START + timedelta(hours=2 * bar_index)
                series.loc[frame.index == signal_at] = True
            frame[column] = series
            yield from signals_from_column(
                frame, column, side=side, symbol="BTC",
            )


def _run(strategy):
    resources = Path(__file__).parent.parent.parent / "resources"
    csv_path = resources / "test_data" / "ohlcv" / CSV_FILENAME
    app = create_app(
        name=f"EventHedge{uuid4().hex}",
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
        engines=[BacktestEngine.EVENT_DRIVEN],
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


class TestEventHedgeMode(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.closed_run = _run(HedgeSignalsStrategy(_both_open_signals({
            SignalSide.CLOSE_LONG: [3],
            SignalSide.CLOSE_SHORT: [4],
        })))
        cls.take_profit_run = _run(HedgeSignalsStrategy(
            _both_open_signals(),
            take_profits=[
                TakeProfitRule(8, 100, "BTC", side="long"),
                TakeProfitRule(10, 100, "BTC", side="short"),
            ],
        ))
        cls.stop_loss_run = _run(HedgeSignalsStrategy(
            _both_open_signals(),
            stop_losses=[
                StopLossRule(10, 100, "BTC", side="long"),
                StopLossRule(8, 100, "BTC", side="short"),
            ],
        ))
        cls.cooldown_run = _run(HedgeSignalsStrategy(
            _both_open_signals({
                SignalSide.CLOSE_LONG: [1],
                SignalSide.CLOSE_SHORT: [1],
            }),
            cooldowns=[CooldownRule(
                symbol="BTC", trigger="buy", blocks="any", bars=3,
            )],
        ))

    def test_simultaneous_long_and_short_open(self):
        trades = self.closed_run.trades
        self.assertEqual(2, len(trades))
        self.assertEqual({False, True}, {trade.is_short for trade in trades})
        self.assertEqual("hedge", self.closed_run.metadata["position_mode"])

    def test_side_specific_pnl_attribution(self):
        long_trade = next(
            trade for trade in self.closed_run.trades if not trade.is_short
        )
        short_trade = next(
            trade for trade in self.closed_run.trades if trade.is_short
        )
        self.assertTrue(TradeStatus.CLOSED.equals(long_trade.status))
        self.assertTrue(TradeStatus.CLOSED.equals(short_trade.status))
        self.assertLess(long_trade.net_gain, 0)
        self.assertGreater(short_trade.net_gain, 0)
        long_close = next(
            order for order in long_trade.orders
            if order.order_side == "SELL"
        )
        short_close = next(
            order for order in short_trade.orders
            if order.order_side == "COVER"
        )
        self.assertAlmostEqual(
            long_trade.net_gain,
            (long_close.price - long_trade.open_price) * long_close.amount,
        )
        self.assertAlmostEqual(
            short_trade.net_gain,
            (short_trade.open_price - short_close.price) * short_close.amount,
        )

    def test_take_profit_closes_each_leg_independently(self):
        long_trade = next(
            trade for trade in self.take_profit_run.trades
            if not trade.is_short
        )
        short_trade = next(
            trade for trade in self.take_profit_run.trades if trade.is_short
        )
        self.assertLess(short_trade.closed_at, long_trade.closed_at)
        self.assertTrue(TradeStatus.CLOSED.equals(long_trade.status))
        self.assertTrue(TradeStatus.CLOSED.equals(short_trade.status))

    def test_stop_loss_closes_each_leg_independently(self):
        long_trade = next(
            trade for trade in self.stop_loss_run.trades
            if not trade.is_short
        )
        short_trade = next(
            trade for trade in self.stop_loss_run.trades if trade.is_short
        )
        self.assertLess(long_trade.closed_at, short_trade.closed_at)
        self.assertTrue(TradeStatus.CLOSED.equals(long_trade.status))
        self.assertTrue(TradeStatus.CLOSED.equals(short_trade.status))

    def test_cooldown_is_independent_per_leg(self):
        long_trade = next(
            trade for trade in self.cooldown_run.trades
            if not trade.is_short
        )
        short_trade = next(
            trade for trade in self.cooldown_run.trades if trade.is_short
        )
        self.assertTrue(TradeStatus.OPEN.equals(long_trade.status))
        self.assertTrue(TradeStatus.CLOSED.equals(short_trade.status))
