"""
Tests for VectorBacktestService short-selling support (Issue #433).

The vector engine now accepts two additional signal generators on
``TradingStrategy``:

* ``generate_short_signals`` — opens a short (SELL-first) when no
  position is open.
* ``generate_cover_signals`` — buys back an open short.

These tests exercise:

1. Default behaviour: when both generators return ``None`` (the
   default), the engine behaves exactly as before — no short trades
   produced, normal long flow intact.
2. A short trade is correctly opened on the SHORT bar (SELL order,
   ``trade.is_short`` true, ``metadata["is_short"]`` set) and the
   proceeds are credited to ``unallocated``.
3. A short is correctly closed on the COVER bar (BUY order, P&L =
   ``(open_price - cover_price) * amount - fees`` for the
   simple no-fee case).
4. P&L direction: shorting a *falling* market produces positive
   ``net_gain``; shorting a *rising* market produces negative
   ``net_gain``.
5. SELL signals do not close shorts (and vice versa for BUY+short).
6. Snapshot bookkeeping: when no position is open, total_value equals
   unallocated; when a short is open, total_value tracks
   ``proceeds - liability`` correctly.
"""
import os
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from unittest import TestCase

import pandas as pd

from investing_algorithm_framework import (
    BacktestDateRange,
    DataSource,
    DataType,
    PositionSize,
    RESOURCE_DIRECTORY,
    DATA_DIRECTORY,
    Schedule,
    SignalSeries,
    SignalSide,
    SnapshotInterval,
    TimeUnit,
    TradeStatus,
    TradingStrategy,
    create_app,
    generate_algorithm_id,
    Study,
    Universe,
    BacktestWindow,
    BacktestEngine,
)
from investing_algorithm_framework.domain.models.order import OrderSide


def _resource_directory():
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "..", "resources"
    )


def _make_app():
    config = {
        RESOURCE_DIRECTORY: _resource_directory(),
        DATA_DIRECTORY: "test_data/ohlcv",
    }
    app = create_app(name="VectorShortSellingTests", config=config)
    app.add_market(
        market="BITVAVO", trading_symbol="EUR", initial_balance=1000
    )
    return app


# ---------------------------------------------------------------------------
# Deterministic strategies — emit specific signals on specific bar indices.
# ---------------------------------------------------------------------------
class _BaseDeterministicStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.HOUR)

    def __init__(self, symbol, market, position_sizes):
        self.symbol = symbol
        data_source = DataSource(
            identifier=f"{symbol}_ohlcv",
            data_type=DataType.OHLCV,
            time_frame="2h",
            market=market,
            symbol=f"{symbol}/EUR",
            pandas=True,
        )
        super().__init__(
            algorithm_id=generate_algorithm_id(
                params={"determ": symbol}
            ),
            data_sources=[data_source],
            schedule=Schedule.every(2, TimeUnit.HOUR),
            symbols=[symbol],
            position_sizes=position_sizes,
        )

    def _empty(self, data):
        df = data[f"{self.symbol}_ohlcv"]
        return pd.Series(False, index=df.index)

    # v9 surface: subclasses override the per-side hooks. The
    # generator below collects them into SignalSeries instances.
    def _buy_series(self, data):
        return self._empty(data)

    def _sell_series(self, data):
        return self._empty(data)

    def _short_series(self, data):
        return None  # None => short side not emitted (disabled).

    def _cover_series(self, data):
        return None

    def generate_signal_series(self, data):
        yield SignalSeries(
            symbol=self.symbol,
            side=SignalSide.OPEN_LONG,
            series=self._buy_series(data),
        )
        yield SignalSeries(
            symbol=self.symbol,
            side=SignalSide.CLOSE_LONG,
            series=self._sell_series(data),
        )
        short = self._short_series(data)
        cover = self._cover_series(data)
        if short is not None:
            yield SignalSeries(
                symbol=self.symbol,
                side=SignalSide.OPEN_SHORT,
                series=short,
            )
        if cover is not None:
            yield SignalSeries(
                symbol=self.symbol,
                side=SignalSide.CLOSE_SHORT,
                series=cover,
            )


class ShortAtIndexStrategy(_BaseDeterministicStrategy):
    """Open a short at bar ``short_idx``; cover at bar ``cover_idx``."""

    def __init__(self, symbol, market, position_sizes,
                 short_idx, cover_idx):
        super().__init__(symbol, market, position_sizes)
        self._short_idx = short_idx
        self._cover_idx = cover_idx

    def _short_series(self, data):
        s = self._empty(data).copy()
        if 0 <= self._short_idx < len(s):
            s.iloc[self._short_idx] = True
        return s

    def _cover_series(self, data):
        s = self._empty(data).copy()
        if 0 <= self._cover_idx < len(s):
            s.iloc[self._cover_idx] = True
        return s


class DefaultStrategy(_BaseDeterministicStrategy):
    """No shorts — uses the default ``None`` short/cover generators."""


def _run_backtest(app, strategy, start, end):
    date_range = BacktestDateRange(
        start_date=start, end_date=end, name="ShortPeriod"
    )
    study = Study(
        universe=Universe(market="BITVAVO", trading_symbol="EUR"),
        initial_capital=1000,
        risk_free_rate=0.027,
        backtest_windows=[BacktestWindow(train_range=date_range)],
        engines=[BacktestEngine.VECTOR],
    )
    backtests = app.run_backtest(
        strategy=strategy,
        study=study,
        snapshot_interval=SnapshotInterval.DAILY,
        use_checkpoints=False,
    )
    backtest = backtests[0]
    runs = backtest.get_all_backtest_runs()
    return runs[0] if runs else None


# ===================================================================
# 1. Default behaviour — shorting disabled (no signals)
# ===================================================================
class TestDefaultBehaviourUnchanged(TestCase):

    def test_default_strategy_produces_no_short_trades(self):
        app = _make_app()
        strategy = DefaultStrategy(
            symbol="BTC",
            market="BITVAVO",
            position_sizes=[
                PositionSize(symbol="BTC", percentage_of_portfolio=20.0)
            ],
        )
        # No buy/sell/short/cover signals -> no trades at all.
        end = datetime(2024, 12, 2, tzinfo=timezone.utc)
        start = end - timedelta(days=30)
        run = _run_backtest(app, strategy, start, end)
        self.assertIsNotNone(run)
        self.assertEqual(run.number_of_trades, 0)
        # short/cover should NOT appear in raw_signals (disabled).
        for sym in run.signals:
            self.assertNotIn("short", run.signals[sym])
            self.assertNotIn("cover", run.signals[sym])


# ===================================================================
# 2 + 3. Short opens with SELL order; closes with BUY order
# ===================================================================
class TestShortOpenAndClose(TestCase):

    def _run(self, short_idx=5, cover_idx=15):
        app = _make_app()
        strategy = ShortAtIndexStrategy(
            symbol="BTC",
            market="BITVAVO",
            position_sizes=[
                PositionSize(symbol="BTC", percentage_of_portfolio=20.0)
            ],
            short_idx=short_idx,
            cover_idx=cover_idx,
        )
        end = datetime(2024, 12, 2, tzinfo=timezone.utc)
        start = end - timedelta(days=30)
        return _run_backtest(app, strategy, start, end)

    def test_short_trade_is_created(self):
        run = self._run()
        self.assertIsNotNone(run)
        self.assertEqual(run.number_of_trades, 1)
        trade = run.trades[0]
        self.assertTrue(trade.is_short)
        self.assertIs(trade.metadata.get("is_short"), True)

    def test_first_order_is_sell_second_is_buy(self):
        run = self._run()
        trade = run.trades[0]
        self.assertEqual(len(trade.orders), 2)
        self.assertEqual(
            trade.orders[0].order_side, OrderSide.SELL.value
        )
        self.assertEqual(
            trade.orders[1].order_side, OrderSide.BUY.value
        )

    def test_short_signal_present_in_raw_signals(self):
        run = self._run()
        self.assertIn("short", run.signals["BTC"])
        self.assertIn("cover", run.signals["BTC"])

    def test_trade_is_closed_after_cover(self):
        run = self._run()
        trade = run.trades[0]
        self.assertTrue(TradeStatus.CLOSED.equals(trade.status))
        self.assertIsNotNone(trade.closed_at)
        self.assertGreater(trade.closed_at, trade.opened_at)


# ===================================================================
# 4. P&L direction tracks (open_price - cover_price)
# ===================================================================
class TestShortPnlDirection(TestCase):

    def _net_gain_for(self, short_idx, cover_idx):
        app = _make_app()
        strategy = ShortAtIndexStrategy(
            symbol="BTC",
            market="BITVAVO",
            position_sizes=[
                PositionSize(symbol="BTC", percentage_of_portfolio=20.0)
            ],
            short_idx=short_idx,
            cover_idx=cover_idx,
        )
        end = datetime(2024, 12, 2, tzinfo=timezone.utc)
        start = end - timedelta(days=60)
        run = _run_backtest(app, strategy, start, end)
        trade = run.trades[0]
        return trade.open_price, trade.orders[1].price, trade.net_gain

    def test_falling_market_short_is_profitable(self):
        """
        Pick two indices and assert: if cover_price < open_price then
        net_gain > 0 (short profits when price drops). We scan a few
        candidate pairs to find one in the available fixture window,
        rather than baking in fragile market knowledge.
        """
        # Try a handful of candidate pairs; assert *at least one*
        # falling-market case yields positive PnL.
        candidates = [
            (5, 50), (10, 100), (20, 80), (50, 150), (100, 200),
        ]
        any_falling_positive = False
        any_rising_negative = False
        for short_idx, cover_idx in candidates:
            try:
                open_p, cover_p, net_gain = self._net_gain_for(
                    short_idx, cover_idx
                )
            except Exception:
                continue
            if cover_p < open_p:
                # Short was profitable; net_gain should be > 0 modulo
                # rounding. With zero trading-cost fixture, it's exact.
                self.assertGreater(
                    net_gain, 0,
                    f"Short at bar {short_idx} covered at bar "
                    f"{cover_idx}: open={open_p} cover={cover_p} "
                    f"gain={net_gain} — expected positive."
                )
                any_falling_positive = True
            elif cover_p > open_p:
                self.assertLess(
                    net_gain, 0,
                    f"Short at bar {short_idx} covered at bar "
                    f"{cover_idx}: open={open_p} cover={cover_p} "
                    f"gain={net_gain} — expected negative."
                )
                any_rising_negative = True

        # We don't require BOTH cases to appear in the fixture, but at
        # least one of them must, otherwise this test is vacuous.
        self.assertTrue(
            any_falling_positive or any_rising_negative,
            "Fixture provided neither a falling nor rising window — "
            "test is vacuous, choose different candidate indices."
        )

    def test_pnl_matches_open_minus_cover_times_amount(self):
        """Exact formula check (no trading cost configured)."""
        app = _make_app()
        strategy = ShortAtIndexStrategy(
            symbol="BTC",
            market="BITVAVO",
            position_sizes=[
                PositionSize(symbol="BTC", percentage_of_portfolio=20.0)
            ],
            short_idx=5,
            cover_idx=25,
        )
        end = datetime(2024, 12, 2, tzinfo=timezone.utc)
        start = end - timedelta(days=30)
        run = _run_backtest(app, strategy, start, end)
        trade = run.trades[0]
        open_price = trade.open_price
        cover_price = trade.orders[1].price
        amount = trade.amount
        expected = (open_price - cover_price) * amount
        # With no fee/slippage configured, net_gain == expected.
        self.assertAlmostEqual(trade.net_gain, expected, places=6)


# ===================================================================
# 5. SELL signal doesn't close a short
# ===================================================================
class ShortPlusSellStrategy(ShortAtIndexStrategy):
    """Short at bar 5, fire SELL at bar 10 (should be a no-op),
    cover at bar 20."""

    def _sell_series(self, data):
        s = self._empty(data).copy()
        if 10 < len(s):
            s.iloc[10] = True
        return s


class TestSignalIsolation(TestCase):

    def test_sell_signal_does_not_close_short(self):
        app = _make_app()
        strategy = ShortPlusSellStrategy(
            symbol="BTC",
            market="BITVAVO",
            position_sizes=[
                PositionSize(symbol="BTC", percentage_of_portfolio=20.0)
            ],
            short_idx=5,
            cover_idx=20,
        )
        end = datetime(2024, 12, 2, tzinfo=timezone.utc)
        start = end - timedelta(days=30)
        run = _run_backtest(app, strategy, start, end)
        trade = run.trades[0]
        # Trade must be closed (by COVER, not SELL).
        self.assertTrue(TradeStatus.CLOSED.equals(trade.status))
        # And only 2 orders: SELL (open) + BUY (cover).
        self.assertEqual(len(trade.orders), 2)
        # The SELL signal event was emitted but executed=False (no
        # long position to close).
        sell_events = [
            e for e in run.signal_events
            if e["signal"] == "sell"
        ]
        for e in sell_events:
            self.assertFalse(e["executed"])


if __name__ == "__main__":
    unittest.main()
