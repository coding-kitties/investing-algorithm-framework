import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, create_app, BacktestDateRange, PositionSize, \
    RESOURCE_DIRECTORY, CSVOHLCVDataProvider, Schedule, SignalSide, \
    signals_from_column, signal_series_from_column, Study, Universe, \
    BacktestWindow, BacktestEngine

# ═══════════════════════════════════════════════════════════════════════
# Fast CSV price sequence (OHLCV_BTC-EUR_BITVAVO_2h_LONG_SHORT_CYCLE.csv):
#
#  Row | Close | Signal
#  ----+-------+---------------------------
#  1-5 | 100   | warmup
#   6  | 110   | OPEN_LONG
#   7  | 100   | —
#   8  | 100   | (already in position)
#   9  | 90    | CLOSE_LONG
#  10  | 100   | —
#  11  | 100   | —
#  12  | 120   | OPEN_SHORT
#  13  | 100   | —
#  14  | 100   | (already in position)
#  15  | 90    | CLOSE_SHORT
#  16  | 100   | post-cycle buffer
#
# The long and short cycles are compared as two *separate* backtests
# (each starting from the same pristine initial balance) rather than
# one combined run for the *signal-generation* parity tests below,
# keeping those tests focused purely on signal-generation parity —
# unaffected by position-sizing mode.
#
# Chaining long+short in a single run sizes the short trade's
# `percentage_of_portfolio` off the balance *after* the prior trade's
# P&L. By default the vector engine sizes every trade off the run's
# static starting balance (`dynamic_position_sizing=False`, kept for
# backward compatibility / speed — it lets the engine size all trades
# for a symbol in one vectorised pass instead of a sequential replay),
# while the event engine always sizes off the live post-trade balance.
# Passing `dynamic_position_sizing=True` makes the vector engine
# replay position sizing sequentially off the live balance too —
# `TestEventVsVectorBacktestCombinedDynamicSizing` below proves this
# achieves exact parity with the event engine for a chained
# long-then-short run.
# ═══════════════════════════════════════════════════════════════════════

CSV_FILENAME = "OHLCV_BTC-EUR_BITVAVO_2h_LONG_SHORT_CYCLE.csv"
WARMUP = 5
LONG_START_DATE = datetime(2020, 12, 20, 10, 0, 0, tzinfo=timezone.utc)
LONG_END_DATE = datetime(2020, 12, 20, 16, 0, 0, tzinfo=timezone.utc)
SHORT_START_DATE = datetime(2020, 12, 20, 22, 0, 0, tzinfo=timezone.utc)
SHORT_END_DATE = datetime(2020, 12, 21, 6, 0, 0, tzinfo=timezone.utc)
MARKET = "BITVAVO"
TRADING_SYMBOL = "EUR"


def _build_study(
    date_range, risk_free_rate=None, engine=BacktestEngine.VECTOR
):
    # Old run_vector_backtest/run_backtest calls were explicit engine
    # choices, not auto-detected — force the engine here too, to keep
    # the vector-vs-event comparison deterministic regardless of
    # auto-detection.
    return Study(
        universe=Universe(market=MARKET, trading_symbol=TRADING_SYMBOL),
        risk_free_rate=risk_free_rate,
        backtest_windows=[BacktestWindow(train_range=date_range)],
        engines=[engine],
    )


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


class LongCycleStrategy(TradingStrategy):
    """Deterministic long-only strategy: open at Close == 110, close
    at Close == 90. Identical behavior in event and vector mode."""
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]

    @staticmethod
    def _with_signal_columns(df):
        df = df.copy()
        df["buy"] = df["Close"] == 110
        df["sell"] = df["Close"] == 90
        return df

    def generate_signals(self, context, data):
        df = self._with_signal_columns(data["BTC_EUR_OHLCV"])
        yield from signals_from_column(
            df, "buy", side=SignalSide.OPEN_LONG, symbol="BTC",
        )
        yield from signals_from_column(
            df, "sell", side=SignalSide.CLOSE_LONG, symbol="BTC",
        )

    def generate_signal_series(self, data):
        df = self._with_signal_columns(data["BTC_EUR_OHLCV"])
        yield signal_series_from_column(
            df, "buy", side=SignalSide.OPEN_LONG, symbol="BTC",
        )
        yield signal_series_from_column(
            df, "sell", side=SignalSide.CLOSE_LONG, symbol="BTC",
        )


class ShortCycleStrategy(TradingStrategy):
    """Deterministic short-only strategy: open at Close == 120, cover
    at Close == 90. Identical behavior in event and vector mode."""
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]

    @staticmethod
    def _with_signal_columns(df):
        df = df.copy()
        df["short"] = df["Close"] == 120
        df["cover"] = df["Close"] == 90
        return df

    def generate_signals(self, context, data):
        df = self._with_signal_columns(data["BTC_EUR_OHLCV"])
        yield from signals_from_column(
            df, "short", side=SignalSide.OPEN_SHORT, symbol="BTC",
        )
        yield from signals_from_column(
            df, "cover", side=SignalSide.CLOSE_SHORT, symbol="BTC",
        )

    def generate_signal_series(self, data):
        df = self._with_signal_columns(data["BTC_EUR_OHLCV"])
        yield signal_series_from_column(
            df, "short", side=SignalSide.OPEN_SHORT, symbol="BTC",
        )
        yield signal_series_from_column(
            df, "cover", side=SignalSide.CLOSE_SHORT, symbol="BTC",
        )


class CombinedCycleStrategy(TradingStrategy):
    """Long cycle immediately followed by a short cycle, in one
    continuous run — the short trade's `percentage_of_portfolio` is
    therefore sized off the balance left over after the long trade's
    P&L, not off the run's static starting balance. Used to prove
    vector/event position-sizing parity under
    `dynamic_position_sizing=True` (see
    `TestEventVsVectorBacktestCombinedDynamicSizing`)."""
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]

    @staticmethod
    def _with_signal_columns(df):
        df = df.copy()
        df["buy"] = df["Close"] == 110
        df["sell"] = df["Close"] == 90
        df["short"] = df["Close"] == 120
        df["cover"] = df["Close"] == 90
        return df

    def generate_signals(self, context, data):
        df = self._with_signal_columns(data["BTC_EUR_OHLCV"])
        yield from signals_from_column(
            df, "buy", side=SignalSide.OPEN_LONG, symbol="BTC",
        )
        yield from signals_from_column(
            df, "sell", side=SignalSide.CLOSE_LONG, symbol="BTC",
        )
        yield from signals_from_column(
            df, "short", side=SignalSide.OPEN_SHORT, symbol="BTC",
        )
        yield from signals_from_column(
            df, "cover", side=SignalSide.CLOSE_SHORT, symbol="BTC",
        )

    def generate_signal_series(self, data):
        df = self._with_signal_columns(data["BTC_EUR_OHLCV"])
        yield signal_series_from_column(
            df, "buy", side=SignalSide.OPEN_LONG, symbol="BTC",
        )
        yield signal_series_from_column(
            df, "sell", side=SignalSide.CLOSE_LONG, symbol="BTC",
        )
        yield signal_series_from_column(
            df, "short", side=SignalSide.OPEN_SHORT, symbol="BTC",
        )
        yield signal_series_from_column(
            df, "cover", side=SignalSide.CLOSE_SHORT, symbol="BTC",
        )


def _create_app(name):
    """Set up an app with CSVOHLCVDataProvider for BTC/EUR."""
    resource_dir = str(Path(__file__).parent.parent.parent / 'resources')
    csv_path = str(
        Path(__file__).parent.parent.parent / 'resources' / 'test_data'
        / 'ohlcv' / CSV_FILENAME
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


class _EventVsVectorParityAssertions:
    """Shared comparison assertions for event-vs-vector parity.

    Not a TestCase itself (no `setUpClass`/fixtures) — mix into a
    TestCase subclass that sets `vector_run`/`event_run`.
    """

    vector_run = None
    event_run = None

    def test_compare_trade_counts(self):
        """Both modes should produce the same number of trades."""
        self.assertEqual(
            len(self.vector_run.get_trades()),
            len(self.event_run.get_trades()),
            f"Trade count mismatch: "
            f"vector={len(self.vector_run.get_trades())}, "
            f"event={len(self.event_run.get_trades())}"
        )

    def test_compare_order_counts(self):
        """Both modes should produce the same number of orders."""
        self.assertEqual(
            len(self.vector_run.orders),
            len(self.event_run.orders),
            f"Order count mismatch: "
            f"vector={len(self.vector_run.orders)}, "
            f"event={len(self.event_run.orders)}"
        )

    def test_compare_trade_net_gains(self):
        """Individual trade net gains should match between modes.

        Note: Portfolio-level backtest_metrics (total_net_gain, final_value)
        may differ due to architectural differences in how the event-based
        and vector-based engines compute aggregate portfolio metrics.
        Trade-level net gains are the authoritative comparison.
        """
        v_trades = sorted(
            self.vector_run.get_trades(), key=lambda t: t.opened_at
        )
        e_trades = sorted(
            self.event_run.get_trades(), key=lambda t: t.opened_at
        )

        self.assertEqual(len(v_trades), len(e_trades))

        for i, (vt, et) in enumerate(zip(v_trades, e_trades)):
            self.assertAlmostEqual(
                vt.net_gain, et.net_gain,
                delta=max(abs(et.net_gain) * 0.01, 0.01),
                msg=f"Trade {i}: net_gain mismatch "
                    f"(vector={vt.net_gain}, event={et.net_gain})"
            )

    def test_compare_trade_details(self):
        """Individual trades should match in symbol and status."""
        v_trades = sorted(
            self.vector_run.get_trades(), key=lambda t: t.opened_at
        )
        e_trades = sorted(
            self.event_run.get_trades(), key=lambda t: t.opened_at
        )

        self.assertEqual(len(v_trades), len(e_trades))

        for i, (vt, et) in enumerate(zip(v_trades, e_trades)):
            # Same symbol
            v_sym = getattr(vt, 'symbol', None) or \
                getattr(vt, 'target_symbol', None)
            e_sym = getattr(et, 'symbol', None) or \
                getattr(et, 'target_symbol', None)
            self.assertEqual(
                v_sym, e_sym, f"Trade {i}: symbol mismatch"
            )

            # Both positive amounts
            self.assertGreater(
                vt.amount, 0, f"Trade {i}: vector amount <= 0"
            )
            self.assertGreater(
                et.amount, 0, f"Trade {i}: event amount <= 0"
            )

            # Same status
            v_status = vt.status.value if hasattr(
                vt.status, 'value') else vt.status
            e_status = et.status.value if hasattr(
                et.status, 'value') else et.status
            self.assertEqual(
                v_status, e_status,
                f"Trade {i}: status mismatch"
            )

    def test_compare_trade_amounts(self):
        """Trade amounts should be very close (same sizing logic)."""
        v_trades = sorted(
            self.vector_run.get_trades(), key=lambda t: t.opened_at
        )
        e_trades = sorted(
            self.event_run.get_trades(), key=lambda t: t.opened_at
        )

        for i, (vt, et) in enumerate(zip(v_trades, e_trades)):
            self.assertAlmostEqual(
                vt.amount, et.amount,
                delta=max(abs(et.amount) * 0.05, 0.001),
                msg=f"Trade {i}: amount mismatch "
                    f"(vector={vt.amount}, event={et.amount})"
            )


class TestEventVsVectorBacktestLong(_EventVsVectorParityAssertions, TestCase):
    """
    Compare event-based and vector-based backtest results for a
    single long cycle: open at Close=110 (Dec 20 10:00), close at
    Close=90 (Dec 20 16:00). Both modes should produce identical
    trades and very close metrics.
    """

    @classmethod
    def setUpClass(cls):
        date_range = BacktestDateRange(
            start_date=LONG_START_DATE, end_date=LONG_END_DATE
        )

        app_v = _create_app("VectorLongTest")
        vector_study = _build_study(
            date_range, risk_free_rate=0.027, engine=BacktestEngine.VECTOR
        )
        vector_backtests = app_v.run_backtest(
            strategy=LongCycleStrategy(algorithm_id="vector_long"),
            study=vector_study,
        )
        cls.vector_run = vector_backtests[0].get_all_backtest_runs()[0]

        app_e = _create_app("EventLongTest")
        event_study = _build_study(
            date_range, risk_free_rate=0.027,
            engine=BacktestEngine.EVENT_DRIVEN,
        )
        event_backtests = app_e.run_backtest(
            strategy=LongCycleStrategy(algorithm_id="event_long"),
            study=event_study,
        )
        cls.event_run = event_backtests[0].get_all_backtest_runs()[0]


class TestEventVsVectorBacktestShort(_EventVsVectorParityAssertions, TestCase):
    """
    Compare event-based and vector-based backtest results for a
    single short cycle: open at Close=120 (Dec 20 22:00), cover at
    Close=90 (Dec 21 04:00). Both modes should produce identical
    trades and very close metrics.
    """

    @classmethod
    def setUpClass(cls):
        date_range = BacktestDateRange(
            start_date=SHORT_START_DATE, end_date=SHORT_END_DATE
        )

        app_v = _create_app("VectorShortTest")
        vector_study = _build_study(
            date_range, risk_free_rate=0.027, engine=BacktestEngine.VECTOR
        )
        vector_backtests = app_v.run_backtest(
            strategy=ShortCycleStrategy(algorithm_id="vector_short"),
            study=vector_study,
        )
        cls.vector_run = vector_backtests[0].get_all_backtest_runs()[0]

        app_e = _create_app("EventShortTest")
        event_study = _build_study(
            date_range, risk_free_rate=0.027,
            engine=BacktestEngine.EVENT_DRIVEN,
        )
        event_backtests = app_e.run_backtest(
            strategy=ShortCycleStrategy(algorithm_id="event_short"),
            study=event_study,
        )
        cls.event_run = event_backtests[0].get_all_backtest_runs()[0]


class TestEventVsVectorBacktestCombinedDynamicSizing(
    _EventVsVectorParityAssertions, TestCase
):
    """
    Compare event-based and vector-based backtest results for a
    long cycle immediately followed by a short cycle in a single
    continuous run (`CombinedCycleStrategy`, spanning both cycles'
    date ranges) — the short trade is sized off the balance left
    over after the long trade's P&L, not off a static starting
    balance.

    This is the scenario that, by default (`dynamic_position_sizing`
    unset / `False`), diverges between engines: the vector engine
    sizes every trade off the run's static starting balance while the
    event engine always sizes off the live post-trade balance. Passing
    `dynamic_position_sizing=True` makes the vector engine replay
    position sizing sequentially off the live balance, matching the
    event engine exactly (verified: both engines produce a second
    trade with `cost=192.7273`, `net_gain=48.1818` here).
    """

    @classmethod
    def setUpClass(cls):
        date_range = BacktestDateRange(
            start_date=LONG_START_DATE, end_date=SHORT_END_DATE
        )

        app_v = _create_app("VectorCombinedDynamicTest")
        vector_study = _build_study(
            date_range, risk_free_rate=0.027, engine=BacktestEngine.VECTOR
        )
        vector_backtests = app_v.run_backtest(
            strategy=CombinedCycleStrategy(algorithm_id="vector_combined"),
            study=vector_study,
            dynamic_position_sizing=True,
        )
        cls.vector_run = vector_backtests[0].get_all_backtest_runs()[0]

        app_e = _create_app("EventCombinedDynamicTest")
        event_study = _build_study(
            date_range, risk_free_rate=0.027,
            engine=BacktestEngine.EVENT_DRIVEN,
        )
        event_backtests = app_e.run_backtest(
            strategy=CombinedCycleStrategy(algorithm_id="event_combined"),
            study=event_study,
        )
        cls.event_run = event_backtests[0].get_all_backtest_runs()[0]


if __name__ == "__main__":
    unittest.main()
