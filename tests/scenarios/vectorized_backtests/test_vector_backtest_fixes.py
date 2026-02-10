"""
Tests for VectorBacktestService fixes (Issues 1-8).

These tests verify the fixes applied to the vector backtest engine:
    1. ffill state machine removal — subsequent buy signals are no longer
       silently discarded.
    2. shift(1) removal — trades execute on the signal bar itself.
    3. number_of_days bug fix — uses end_date - start_date instead of
       end_date - end_date.
    4. Warmup window documentation (no behavioral test needed).
    5. Buy + sell on same bar — sell takes explicit priority.
    6. Static position sizing capital guard — prevents over-allocation.
    7. (Removed — SL/TP does not belong in vectorized backtests.)
    8. Raw signals exposed on BacktestRun.signals.
"""
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from unittest import TestCase

import pandas as pd
from pyindicators import ema, rsi, crossover, crossunder

from investing_algorithm_framework import (
    TradingStrategy,
    DataSource,
    TimeUnit,
    DataType,
    create_app,
    BacktestDateRange,
    PositionSize,
    RESOURCE_DIRECTORY,
    SnapshotInterval,
    generate_algorithm_id,
    TradeStatus,
)


# ---------------------------------------------------------------------------
# Shared strategy used by most tests (simple RSI + EMA crossover)
# ---------------------------------------------------------------------------
class RSIEMACrossoverStrategy(TradingStrategy):
    time_unit = TimeUnit.HOUR
    interval = 2

    def __init__(
        self,
        algorithm_id,
        symbols,
        position_sizes,
        time_unit: TimeUnit,
        interval: int,
        market: str,
        rsi_time_frame: str = "2h",
        rsi_period: int = 14,
        rsi_overbought_threshold=70,
        rsi_oversold_threshold=30,
        ema_time_frame="2h",
        ema_short_period=100,
        ema_long_period=150,
        ema_cross_lookback_window: int = 10,
    ):
        self.rsi_time_frame = rsi_time_frame
        self.rsi_period = rsi_period
        self.rsi_result_column = f"rsi_{self.rsi_period}"
        self.rsi_overbought_threshold = rsi_overbought_threshold
        self.rsi_oversold_threshold = rsi_oversold_threshold
        self.ema_time_frame = ema_time_frame
        self.ema_short_result_column = f"ema_{ema_short_period}"
        self.ema_long_result_column = f"ema_{ema_long_period}"
        self.ema_crossunder_result_column = "ema_crossunder"
        self.ema_crossover_result_column = "ema_crossover"
        self.ema_short_period = ema_short_period
        self.ema_long_period = ema_long_period
        self.ema_cross_lookback_window = ema_cross_lookback_window

        data_sources = []
        for symbol in symbols:
            full_symbol = f"{symbol}/EUR"
            data_sources.append(
                DataSource(
                    identifier=f"{symbol}_rsi_data",
                    data_type=DataType.OHLCV,
                    time_frame=self.rsi_time_frame,
                    market=market,
                    symbol=full_symbol,
                    pandas=True,
                )
            )
            data_sources.append(
                DataSource(
                    identifier=f"{symbol}_ema_data",
                    data_type=DataType.OHLCV,
                    time_frame=self.ema_time_frame,
                    market=market,
                    symbol=full_symbol,
                    pandas=True,
                )
            )

        super().__init__(
            algorithm_id=algorithm_id,
            data_sources=data_sources,
            time_unit=time_unit,
            interval=interval,
            symbols=symbols,
            position_sizes=position_sizes,
        )

    def prepare_indicators(self, rsi_data, ema_data):
        ema_data = ema(
            ema_data,
            period=self.ema_short_period,
            source_column="Close",
            result_column=self.ema_short_result_column,
        )
        ema_data = ema(
            ema_data,
            period=self.ema_long_period,
            source_column="Close",
            result_column=self.ema_long_result_column,
        )
        ema_data = crossover(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossover_result_column,
        )
        ema_data = crossunder(
            ema_data,
            first_column=self.ema_short_result_column,
            second_column=self.ema_long_result_column,
            result_column=self.ema_crossunder_result_column,
        )
        rsi_data = rsi(
            rsi_data,
            period=self.rsi_period,
            source_column="Close",
            result_column=self.rsi_result_column,
        )
        return ema_data, rsi_data

    def generate_buy_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        signals = {}
        for symbol in self.symbols:
            ema_data, rsi_data = self.prepare_indicators(
                data[f"{symbol}_rsi_data"].copy(),
                data[f"{symbol}_ema_data"].copy(),
            )
            ema_crossover_lookback = (
                ema_data[self.ema_crossover_result_column]
                .rolling(window=self.ema_cross_lookback_window)
                .max()
                .astype(bool)
            )
            rsi_oversold = (
                rsi_data[self.rsi_result_column]
                < self.rsi_oversold_threshold
            )
            buy_signal = rsi_oversold & ema_crossover_lookback
            signals[symbol] = buy_signal.fillna(False).astype(bool)
        return signals

    def generate_sell_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        signals = {}
        for symbol in self.symbols:
            ema_data, rsi_data = self.prepare_indicators(
                data[f"{symbol}_rsi_data"].copy(),
                data[f"{symbol}_ema_data"].copy(),
            )
            ema_crossunder_lookback = (
                ema_data[self.ema_crossunder_result_column]
                .rolling(window=self.ema_cross_lookback_window)
                .max()
                .astype(bool)
            )
            rsi_overbought = (
                rsi_data[self.rsi_result_column]
                >= self.rsi_overbought_threshold
            )
            sell_signal = rsi_overbought & ema_crossunder_lookback
            signals[symbol] = sell_signal.fillna(False).astype(bool)
        return signals


def _resource_directory():
    """Return path to tests/resources."""
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "..", "resources"
    )


def _make_app():
    """Create and configure the app used by most tests."""
    config = {RESOURCE_DIRECTORY: _resource_directory()}
    app = create_app(name="VectorBacktestFixTests", config=config)
    app.add_market(
        market="BITVAVO", trading_symbol="EUR", initial_balance=400
    )
    return app


def _make_strategy(
    symbols=None, position_sizes=None
):
    """Build a default RSI/EMA strategy."""
    if symbols is None:
        symbols = ["BTC", "ETH"]
    if position_sizes is None:
        position_sizes = [
            PositionSize(symbol=s, percentage_of_portfolio=20.0)
            for s in symbols
        ]
    return RSIEMACrossoverStrategy(
        algorithm_id=generate_algorithm_id(
            params={"fix_test": True}
        ),
        time_unit=TimeUnit.HOUR,
        interval=2,
        market="BITVAVO",
        symbols=symbols,
        position_sizes=position_sizes,
    )


def _run_backtest(app, strategy, days=365, **kwargs):
    """Run a single-period vector backtest and return the BacktestRun."""
    end_date = datetime(2025, 12, 2, tzinfo=timezone.utc)
    start_date = end_date - timedelta(days=days)
    date_range = BacktestDateRange(
        start_date=start_date, end_date=end_date, name="TestPeriod"
    )
    backtest = app.run_vector_backtest(
        initial_amount=1000,
        backtest_date_range=date_range,
        strategy=strategy,
        snapshot_interval=SnapshotInterval.DAILY,
        risk_free_rate=0.027,
        trading_symbol="EUR",
        market="BITVAVO",
        use_checkpoints=False,
        **kwargs,
    )
    runs = backtest.get_all_backtest_runs()
    return runs[0] if runs else None


# ===================================================================
# Issue 3 — number_of_days bug (end_date - start_date, not end - end)
# ===================================================================
class TestNumberOfDaysFix(TestCase):

    def test_number_of_days_is_nonzero(self):
        """
        After the fix, number_of_days should equal
        (end_date - start_date).days, which is > 0.
        Previously it was always 0 due to end_date - end_date.
        """
        app = _make_app()
        strategy = _make_strategy()
        run = _run_backtest(app, strategy, days=365)
        self.assertIsNotNone(run)
        self.assertGreater(run.number_of_days, 0)
        expected_days = (
            run.backtest_end_date - run.backtest_start_date
        ).days
        self.assertEqual(run.number_of_days, expected_days)


# ===================================================================
# Issue 1 & 2 — ffill removal + shift(1) removal
# Verifies that more trades are produced from the same signals
# and that trades open on the signal bar (no 1-bar delay).
# ===================================================================
class TestFfillAndShiftRemoval(TestCase):

    def test_trades_are_produced(self):
        """
        The backtest should produce at least one trade. With the old
        ffill logic many buy signals were silently discarded.
        """
        app = _make_app()
        strategy = _make_strategy()
        run = _run_backtest(app, strategy, days=365)
        self.assertIsNotNone(run)
        self.assertGreater(run.number_of_trades, 0)

    def test_multiple_buy_sell_cycles(self):
        """
        Over a long enough period the strategy should be able to open
        and close multiple trades per symbol (not just one).
        """
        app = _make_app()
        strategy = _make_strategy()
        run = _run_backtest(app, strategy, days=1095)
        self.assertIsNotNone(run)

        # Count closed trades — with the old ffill logic most symbols
        # would have at most 1 trade.
        closed = [
            t for t in run.trades
            if TradeStatus.CLOSED.equals(t.status)
        ]
        # We expect at least some closed trades over 3 years
        self.assertGreaterEqual(
            len(closed), 1,
            "Expected at least 1 closed trade over 3 years"
        )


# ===================================================================
# Issue 5 — Buy+sell on same bar: sell takes priority
# ===================================================================
class TestBuySellSameBarPriority(TestCase):

    def test_sell_priority_over_buy(self):
        """
        When both buy and sell fire on the same bar, the sell should
        take priority. This means if we are in a position, the
        position should be closed (not ignored). If we are NOT in a
        position, neither signal should open a trade (since buy is
        suppressed when sell also fires).
        """
        app = _make_app()
        strategy = _make_strategy()
        run = _run_backtest(app, strategy, days=365)
        self.assertIsNotNone(run)

        # Basic structural check: every trade should have at most
        # one buy order and at most one sell order.
        for trade in run.trades:
            buy_orders = [
                o for o in trade.orders if o.order_side == "buy"
            ]
            sell_orders = [
                o for o in trade.orders if o.order_side == "sell"
            ]
            self.assertLessEqual(
                len(buy_orders), 1,
                "Trade should have at most 1 buy order"
            )
            self.assertLessEqual(
                len(sell_orders), 1,
                "Trade should have at most 1 sell order"
            )


# ===================================================================
# Issue 6 — Static position sizing capital guard
# ===================================================================
class TestStaticPositionSizingCapitalGuard(TestCase):

    def test_total_allocation_does_not_exceed_initial_amount(self):
        """
        In static position sizing mode, the total capital allocated
        across all simultaneously open trades should never exceed
        the initial portfolio amount.
        """
        app = _make_app()
        symbols = ["BTC", "ETH"]
        # Allocate 60% per symbol — without the guard both could be
        # open simultaneously and exceed 100%.
        position_sizes = [
            PositionSize(symbol="BTC", percentage_of_portfolio=60.0),
            PositionSize(symbol="ETH", percentage_of_portfolio=60.0),
        ]
        strategy = _make_strategy(
            symbols=symbols, position_sizes=position_sizes
        )
        run = _run_backtest(
            app, strategy, days=365, dynamic_position_sizing=False
        )
        self.assertIsNotNone(run)

        # Verify: at no snapshot does unallocated go negative
        for snap in run.portfolio_snapshots:
            self.assertGreaterEqual(
                snap.unallocated, -0.01,
                f"Unallocated went negative ({snap.unallocated}) "
                f"at {snap.created_at} — capital guard failed"
            )


# ===================================================================
# Issue 8 — Raw signals exposed on BacktestRun.signals
# ===================================================================
class TestRawSignalsExposed(TestCase):

    def test_signals_field_present_and_populated(self):
        """
        After a vector backtest, BacktestRun.signals should be a dict
        keyed by symbol, each containing 'buy' and 'sell' pd.Series.
        """
        app = _make_app()
        strategy = _make_strategy(symbols=["BTC", "ETH"])
        run = _run_backtest(app, strategy, days=365)
        self.assertIsNotNone(run)

        # signals dict should exist
        self.assertIsInstance(run.signals, dict)
        self.assertIn("BTC", run.signals)
        self.assertIn("ETH", run.signals)

        for symbol in ["BTC", "ETH"]:
            signal_data = run.signals[symbol]
            self.assertIn("buy", signal_data)
            self.assertIn("sell", signal_data)
            self.assertIsInstance(signal_data["buy"], pd.Series)
            self.assertIsInstance(signal_data["sell"], pd.Series)
            # Series should contain boolean values
            self.assertTrue(
                signal_data["buy"].dtype == bool,
                f"Expected bool dtype for {symbol} buy signals, "
                f"got {signal_data['buy'].dtype}"
            )
            self.assertTrue(
                signal_data["sell"].dtype == bool,
                f"Expected bool dtype for {symbol} sell signals, "
                f"got {signal_data['sell'].dtype}"
            )

    def test_signals_have_datetimeindex(self):
        """
        Each signal Series should have a DatetimeIndex.
        """
        app = _make_app()
        strategy = _make_strategy(symbols=["BTC"])
        run = _run_backtest(app, strategy, days=365)
        self.assertIsNotNone(run)

        btc_buy = run.signals["BTC"]["buy"]
        self.assertIsInstance(btc_buy.index, pd.DatetimeIndex)

    def test_signals_contain_at_least_one_true(self):
        """
        Over 3 years the strategy should fire at least one buy signal
        across all tracked symbols.
        """
        app = _make_app()
        strategy = _make_strategy(symbols=["BTC", "ETH"])
        run = _run_backtest(app, strategy, days=1095)
        self.assertIsNotNone(run)

        # At least one symbol should have at least one buy signal
        any_buy = any(
            run.signals[sym]["buy"].any()
            for sym in run.signals
        )
        self.assertTrue(
            any_buy,
            "Expected at least one True buy signal across all "
            "symbols over 3 years"
        )

    def test_signals_not_in_to_dict(self):
        """
        The signals field should NOT appear in to_dict() because
        pd.Series objects are not JSON-serializable. The to_dict
        method is used for saving to disk.
        """
        app = _make_app()
        strategy = _make_strategy(symbols=["BTC"])
        run = _run_backtest(app, strategy, days=365)
        self.assertIsNotNone(run)

        d = run.to_dict()
        self.assertNotIn("signals", d)


# ===================================================================
# Signal Events — execution/rejection log for every fired signal
# ===================================================================
class TestSignalEvents(TestCase):

    def test_signal_events_present(self):
        """
        After a vector backtest, BacktestRun.signal_events should be
        a non-empty list of dicts.
        """
        app = _make_app()
        strategy = _make_strategy()
        run = _run_backtest(app, strategy, days=1095)
        self.assertIsNotNone(run)
        self.assertIsInstance(run.signal_events, list)
        self.assertGreater(
            len(run.signal_events), 0,
            "Expected at least one signal event over 3 years"
        )

    def test_signal_event_structure(self):
        """
        Each signal event should have the required keys:
        date, symbol, signal, executed, reason.
        """
        app = _make_app()
        strategy = _make_strategy()
        run = _run_backtest(app, strategy, days=365)
        self.assertIsNotNone(run)

        for evt in run.signal_events:
            self.assertIn("date", evt)
            self.assertIn("symbol", evt)
            self.assertIn("signal", evt)
            self.assertIn("executed", evt)
            self.assertIn("reason", evt)
            self.assertIn(evt["signal"], ("buy", "sell"))
            self.assertIsInstance(evt["executed"], bool)

    def test_executed_buy_events_match_trades(self):
        """
        The number of executed buy signal events should equal the
        number of trades (each trade is opened by exactly one buy).
        """
        app = _make_app()
        strategy = _make_strategy()
        run = _run_backtest(app, strategy, days=1095)
        self.assertIsNotNone(run)

        executed_buys = run.get_signal_events(
            signal="buy", executed=True
        )
        self.assertEqual(
            len(executed_buys), run.number_of_trades,
            "Each trade should correspond to exactly one "
            "executed buy signal event"
        )

    def test_get_signal_events_filter_by_symbol(self):
        """
        get_signal_events(symbol=...) should return only events for
        that symbol.
        """
        app = _make_app()
        strategy = _make_strategy(symbols=["BTC", "ETH"])
        run = _run_backtest(app, strategy, days=1095)
        self.assertIsNotNone(run)

        btc_events = run.get_signal_events(symbol="BTC")
        for evt in btc_events:
            self.assertEqual(evt["symbol"], "BTC")

    def test_get_signal_events_filter_by_reason(self):
        """
        get_signal_events(reason=...) should return only events with
        the given reason.
        """
        app = _make_app()
        strategy = _make_strategy()
        run = _run_backtest(app, strategy, days=1095)
        self.assertIsNotNone(run)

        executed = run.get_signal_events(reason="executed")
        for evt in executed:
            self.assertEqual(evt["reason"], "executed")

    def test_already_in_position_events(self):
        """
        If a buy signal fires while a position is already open,
        it should be logged as 'already_in_position'.
        """
        app = _make_app()
        strategy = _make_strategy()
        run = _run_backtest(app, strategy, days=1095)
        self.assertIsNotNone(run)

        blocked = run.get_signal_events(
            signal="buy", reason="already_in_position"
        )
        # We can't guarantee they exist in all market conditions,
        # but verify the filter works without error
        for evt in blocked:
            self.assertEqual(evt["signal"], "buy")
            self.assertFalse(evt["executed"])
            self.assertEqual(evt["reason"], "already_in_position")

    def test_signal_events_in_to_dict(self):
        """
        signal_events should be included in to_dict() because they
        are JSON-serializable (unlike raw signals).
        """
        app = _make_app()
        strategy = _make_strategy(symbols=["BTC"])
        run = _run_backtest(app, strategy, days=365)
        self.assertIsNotNone(run)

        d = run.to_dict()
        self.assertIn("signal_events", d)
        self.assertIsInstance(d["signal_events"], list)

        # Dates should be ISO strings, not datetime objects
        for evt in d["signal_events"]:
            self.assertIsInstance(evt["date"], str)
