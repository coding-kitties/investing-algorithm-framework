"""#434 phase 4 — end-to-end event-driven backtest with short selling.

Verifies that overriding ``generate_short_signals`` /
``generate_cover_signals`` on a ``TradingStrategy`` produces SHORT
and COVER orders through the event-driven engine (not just the
vector engine), realises P&L on the cover fill, and persists
``Trade.is_short`` correctly.
"""
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

from investing_algorithm_framework import (
    BacktestDateRange,
    CSVOHLCVDataProvider,
    DataSource,
    DataType,
    PositionSize,
    RESOURCE_DIRECTORY,
    Schedule,
    SignalSide,
    StopLossRule,
    TimeUnit,
    TradingStrategy,
    create_app,
    signals_from_column,
    Study,
    Universe,
    BacktestWindow,
    BacktestEngine,
)


CSV_FILENAME = "OHLCV_BTC-EUR_BITVAVO_2h_SCALING_FAST.csv"
WARMUP = 5
START_DATE = datetime(2020, 12, 20, 10, 0, 0, tzinfo=timezone.utc)
END_DATE = datetime(2020, 12, 21, 22, 0, 0, tzinfo=timezone.utc)


def _make_data_source():
    return DataSource(
        symbol="BTC/EUR",
        data_type=DataType.OHLCV,
        time_frame="2h",
        warmup_window=WARMUP,
        market="BITVAVO",
        identifier="BTC_EUR_OHLCV",
        pandas=True,
    )


class ShortAt120CoverAt90Strategy(TradingStrategy):
    """Open a SHORT when Close == 120, cover when Close == 90."""
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]

    def generate_signals(self, context, data):
        df = data["BTC_EUR_OHLCV"]
        df = df.copy()
        df["short"] = df["Close"] == 120
        df["cover"] = df["Close"] == 90
        yield from signals_from_column(
            df, "short", side=SignalSide.OPEN_SHORT, symbol="BTC",
        )
        yield from signals_from_column(
            df, "cover", side=SignalSide.CLOSE_SHORT, symbol="BTC",
        )


class ShortWithStopLossStrategy(TradingStrategy):
    """Open a SHORT at 120 with a 5% stop loss (triggers at 126).
    The CSV never rises above 120, so the SL never triggers — but
    a cover at 90 closes the trade for a profit."""
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]
    stop_losses = [
        StopLossRule(
            symbol="BTC", percentage_threshold=5, sell_percentage=100,
        ),
    ]

    def generate_signals(self, context, data):
        df = data["BTC_EUR_OHLCV"]
        df = df.copy()
        df["short"] = df["Close"] == 120
        df["cover"] = df["Close"] == 90
        yield from signals_from_column(
            df, "short", side=SignalSide.OPEN_SHORT, symbol="BTC",
        )
        yield from signals_from_column(
            df, "cover", side=SignalSide.CLOSE_SHORT, symbol="BTC",
        )


def _create_app(name):
    resource_dir = str(Path(__file__).parent.parent.parent / "resources")
    csv_path = str(
        Path(__file__).parent.parent.parent / "resources" / "test_data"
        / "ohlcv" / CSV_FILENAME
    )
    app = create_app(
        name=name, config={RESOURCE_DIRECTORY: resource_dir}
    )
    app.add_market(
        market="BITVAVO", trading_symbol="EUR", initial_balance=1000
    )
    app.add_data_provider(
        data_provider=CSVOHLCVDataProvider(
            storage_path=csv_path,
            symbol="BTC/EUR",
            time_frame="2h",
            market="BITVAVO",
            warmup_window=WARMUP,
        ),
        priority=1,
    )
    return app


class TestEventBacktestShortSelling(TestCase):
    """End-to-end: short@120, cover@90 via the event engine."""

    backtest_run = None

    @classmethod
    def setUpClass(cls):
        date_range = BacktestDateRange(
            start_date=START_DATE, end_date=END_DATE
        )
        app = _create_app("EventShortSelling")
        study = Study(
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            risk_free_rate=0.027,
            backtest_windows=[BacktestWindow(train_range=date_range)],
            engines=[BacktestEngine.EVENT_DRIVEN],
        )
        backtests = app.run_backtest(
            strategy=ShortAt120CoverAt90Strategy(
                algorithm_id="event_short"
            ),
            study=study,
        )
        cls.backtest_run = backtests[0].get_all_backtest_runs()[0]

    def test_short_and_cover_orders_exist(self):
        orders = self.backtest_run.orders
        short_orders = [o for o in orders if o.order_side == "SHORT"]
        cover_orders = [o for o in orders if o.order_side == "COVER"]
        self.assertEqual(1, len(short_orders))
        self.assertEqual(1, len(cover_orders))

    def test_short_trade_is_marked_is_short(self):
        trades = self.backtest_run.trades
        self.assertEqual(1, len(trades))
        trade = trades[0]
        self.assertTrue(trade.is_short)

    def test_short_trade_realizes_profit_on_falling_market(self):
        trades = self.backtest_run.trades
        trade = trades[0]
        # Opened at 120, covered at 90 → net_gain = 30 * amount > 0.
        self.assertGreater(trade.net_gain, 0)
        self.assertEqual(120, trade.open_price)

    def test_orders_carry_short_cover_order_reasons(self):
        orders = self.backtest_run.orders
        short_orders = [o for o in orders if o.order_side == "SHORT"]
        cover_orders = [o for o in orders if o.order_side == "COVER"]
        self.assertEqual(
            "short_signal",
            short_orders[0].metadata.get("order_reason"),
        )
        self.assertEqual(
            "cover_signal",
            cover_orders[0].metadata.get("order_reason"),
        )


class TestEventBacktestShortWithStopLoss(TestCase):
    """SL/TP rule on a SHORT trade is materialized with
    ``is_short=True`` so the inverted trigger math kicks in."""

    backtest_run = None

    @classmethod
    def setUpClass(cls):
        date_range = BacktestDateRange(
            start_date=START_DATE, end_date=END_DATE
        )
        app = _create_app("EventShortStopLoss")
        study = Study(
            universe=Universe(market="BITVAVO", trading_symbol="EUR"),
            risk_free_rate=0.027,
            backtest_windows=[BacktestWindow(train_range=date_range)],
            engines=[BacktestEngine.EVENT_DRIVEN],
        )
        backtests = app.run_backtest(
            strategy=ShortWithStopLossStrategy(
                algorithm_id="event_short_sl"
            ),
            study=study,
        )
        cls.backtest_run = backtests[0].get_all_backtest_runs()[0]

    def test_stop_loss_attached_to_short_trade_is_inverted(self):
        trades = self.backtest_run.trades
        self.assertEqual(1, len(trades))
        trade = trades[0]
        self.assertTrue(trade.is_short)
        self.assertEqual(1, len(trade.stop_losses))
        sl = trade.stop_losses[0]
        self.assertTrue(sl.is_short)
        # SL sits 5% ABOVE the entry for shorts.
        self.assertAlmostEqual(120 * 1.05, sl.stop_loss_price)
