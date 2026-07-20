"""
Deterministic P&L scenarios for the backtest engines.

These tests pin down EXACT trade-by-trade outcomes for the framework
using engineered CSV price fixtures where every bar is a flat candle
(``Open == High == Low == Close``). With slippage = 0 and fees = 0 the
engine becomes a closed-form simulator and we can assert exact entry /
exit prices, per-trade net gains and the resulting portfolio cash
balance without any tolerances.

The LONG fixture exercises three deterministic trade outcomes inside a
single event-mode backtest:

  1. **Take-Profit close** — TP triggers on bar 7 (Close 150 ≥ 150).
  2. **Stop-Loss close**   — SL triggers on bar 11 (Close 75 ≤ 75).
  3. **Signal-driven close** — manual CLOSE_LONG fires on bar 15
     (Close 90) which is below TP and above SL.

A separate ``TestDeterministicLongEventScenarioWithCooldown`` reuses
the same fixture but installs a ``CooldownRule`` that blocks the
second BUY signal, leaving exactly two completed trades.

LONG trade arithmetic (no fees, no slippage, ``fixed_amount=200`` →
amount = 2 BTC per trade, take-profit = +50 %, stop-loss = -25 %):

    Trade 1: 2 × (150 − 100) = +100.00 EUR
    Trade 2: 2 × ( 75 − 100) = − 50.00 EUR
    Trade 3: 2 × ( 90 − 100) = − 20.00 EUR
    Total net gain          = + 30.00 EUR
    Final cash               = 1030.00 EUR

The full LONG / SHORT × event / vector matrix is exercised — all four
combinations now produce identical trade-level P&L for fixed-percentage
TP / SL rules. Trailing TP / SL is intentionally not yet supported by
the vector engine; strategies that need trailing rules should run in
event mode.
"""
import unittest
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from unittest import TestCase

from investing_algorithm_framework import (
    BacktestDateRange,
    CooldownBlocks,
    CooldownRule,
    CooldownTrigger,
    CSVOHLCVDataProvider,
    DataSource,
    DataType,
    PositionSize,
    RESOURCE_DIRECTORY,
    Schedule,
    SignalSide,
    StopLossRule,
    TakeProfitRule,
    TimeUnit,
    TradingStrategy,
    create_app,
)
from investing_algorithm_framework.domain.models.signal_helpers import (
    signal_series_from_column,
    signals_from_column,
)


# ─────────────────────────────────────────────────────────────────────
# Fixture metadata. Both fixtures are 18 rows of 2-hour OHLCV with
# Open = High = Low = Close on every bar. The percentages are chosen so
# that ``open_price × (1 ± pct/100)`` is exactly representable in
# IEEE-754 binary floats — 10 % and 5 % are NOT (e.g.
# ``100 * 1.10 == 110.00000000000001``), which causes fixed TP checks
# to miss bars whose Close equals the threshold.
# ─────────────────────────────────────────────────────────────────────

WARMUP = 5
FIXED_ALLOC_EUR = 200.0
INITIAL_BALANCE_EUR = 1000.0
TP_PERCENTAGE = 50.0
SL_PERCENTAGE = 25.0

LONG_CSV = "OHLCV_BTC-EUR_BITVAVO_2h_DET_LONG.csv"
LONG_START = datetime(2021, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
LONG_END = datetime(2021, 1, 2, 10, 0, 0, tzinfo=timezone.utc)
LONG_ENTRY_PRICE = 100.0
LONG_TP_PRICE = LONG_ENTRY_PRICE * (1 + TP_PERCENTAGE / 100)   # 150.0
LONG_SL_PRICE = LONG_ENTRY_PRICE * (1 - SL_PERCENTAGE / 100)   # 75.0
LONG_SIGNAL_EXIT_PRICE = 90.0
LONG_AMOUNT = FIXED_ALLOC_EUR / LONG_ENTRY_PRICE               # 2.0

SHORT_CSV = "OHLCV_BTC-EUR_BITVAVO_2h_DET_SHORT.csv"
SHORT_START = datetime(2021, 2, 1, 10, 0, 0, tzinfo=timezone.utc)
SHORT_END = datetime(2021, 2, 2, 10, 0, 0, tzinfo=timezone.utc)
SHORT_ENTRY_PRICE = 100.0
SHORT_TP_PRICE = SHORT_ENTRY_PRICE * (1 - TP_PERCENTAGE / 100)  # 50.0
SHORT_SL_PRICE = SHORT_ENTRY_PRICE * (1 + SL_PERCENTAGE / 100)  # 125.0
SHORT_SIGNAL_EXIT_PRICE = 110.0
SHORT_AMOUNT = FIXED_ALLOC_EUR / SHORT_ENTRY_PRICE              # 2.0


def _resource_dir() -> str:
    return str(Path(__file__).parent.parent / "resources")


def _csv_path(filename: str) -> str:
    return str(
        Path(__file__).parent.parent / "resources" / "test_data"
        / "ohlcv" / filename
    )


# ─────────────────────────────────────────────────────────────────────
# Strategies
# ─────────────────────────────────────────────────────────────────────

class DeterministicLongStrategy(TradingStrategy):
    """Buys BTC when ``Close == 100``; exits via TP (+50 %),
    SL (-25 %), or a manual CLOSE_LONG signal when ``Close == 90``.
    The same boolean columns drive both the event-mode hook
    (``generate_signals``) and the vector-mode hook
    (``generate_signal_series``)."""

    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [
        DataSource(
            symbol="BTC/EUR",
            data_type=DataType.OHLCV,
            time_frame="2h",
            warmup_window=WARMUP,
            market="BITVAVO",
            identifier="BTC_EUR_OHLCV",
            pandas=True,
        ),
    ]
    position_sizes = [
        PositionSize(symbol="BTC", fixed_amount=FIXED_ALLOC_EUR),
    ]
    stop_losses = [
        StopLossRule(
            symbol="BTC", percentage_threshold=SL_PERCENTAGE,
            trailing=False, sell_percentage=100,
        ),
    ]
    take_profits = [
        TakeProfitRule(
            symbol="BTC", percentage_threshold=TP_PERCENTAGE,
            trailing=False, sell_percentage=100,
        ),
    ]

    @staticmethod
    def _annotate(df):
        df = df.copy()
        df["buy_signal"] = df["Close"] == LONG_ENTRY_PRICE
        df["sell_signal"] = df["Close"] == LONG_SIGNAL_EXIT_PRICE
        return df

    def generate_signals(self, context, data: Dict[str, Any]):
        df = self._annotate(data["BTC_EUR_OHLCV"])
        yield from signals_from_column(
            df, "buy_signal",
            side=SignalSide.OPEN_LONG, symbol="BTC",
            source="deterministic_long",
        )
        yield from signals_from_column(
            df, "sell_signal",
            side=SignalSide.CLOSE_LONG, symbol="BTC",
            source="deterministic_long",
        )

    def generate_signal_series(self, data: Dict[str, Any]):
        df = self._annotate(data["BTC_EUR_OHLCV"])
        yield signal_series_from_column(
            df, "buy_signal",
            side=SignalSide.OPEN_LONG, symbol="BTC",
            source="deterministic_long",
        )
        yield signal_series_from_column(
            df, "sell_signal",
            side=SignalSide.CLOSE_LONG, symbol="BTC",
            source="deterministic_long",
        )


class DeterministicLongWithCooldownStrategy(DeterministicLongStrategy):
    """Same as :class:`DeterministicLongStrategy` but adds a cooldown
    that blocks BUY signals for 5 bars after every BUY fill. The
    second BUY (4 ticks after the first) lands inside the cooldown
    window and is suppressed, while the third BUY (8 ticks later) is
    well past the cooldown and proceeds normally. The backtest yields
    exactly two trades: the TP-closed first trade and the manually-
    closed third trade.

    Cooldown semantics: with ``bars=N`` the rule blocks signals whose
    bar index satisfies ``current - last < N``. For ``N = 5`` the rule
    blocks the next 4 ticks after the trigger, so a signal exactly
    4 ticks later is still blocked but one 5 ticks later is allowed."""

    cooldowns = [
        CooldownRule(
            symbol="BTC",
            trigger=CooldownTrigger.BUY,
            blocks=CooldownBlocks.BUY,
            bars=5,
        ),
    ]


class DeterministicLongWithSellCooldownStrategy(DeterministicLongStrategy):
    """Variant that arms its cooldown off the SELL side. With the
    framework's system-exit recording in
    :class:`RecordCooldownPhase`, TP / SL fills now arm cooldowns the
    same as signal-driven exits.

    Timing on the LONG fixture (1 tick = 1 strategy run):

    * tick 0: BUY signal — opens trade 1 (entry @ 100)
    * tick 2: bar Close = 150 ⇒ TP triggers, LIMIT SELL @ 150 created.
      The RecordCooldownPhase records this as a SELL at tick 2.
    * tick 4: BUY signal #2. With ``bars=4`` the gate checks
      ``4 - 2 = 2 < 4`` ⇒ BLOCKED.
    * tick 8: BUY signal #3. ``8 - 2 = 6 < 4`` is False ⇒ allowed.
    * tick 11: manual SELL signal closes trade 3 @ 90.

    Result: two closed trades. The SL trade (which would have opened
    at tick 4) never happens."""

    cooldowns = [
        CooldownRule(
            symbol="BTC",
            trigger=CooldownTrigger.SELL,
            blocks=CooldownBlocks.BUY,
            bars=4,
        ),
    ]


class DeterministicShortStrategy(TradingStrategy):
    """Mirror of the LONG strategy that shorts BTC when ``Close == 100``
    and covers when ``Close == 110`` (also via TP / SL)."""

    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [
        DataSource(
            symbol="BTC/EUR",
            data_type=DataType.OHLCV,
            time_frame="2h",
            warmup_window=WARMUP,
            market="BITVAVO",
            identifier="BTC_EUR_OHLCV",
            pandas=True,
        ),
    ]
    position_sizes = [
        PositionSize(symbol="BTC", fixed_amount=FIXED_ALLOC_EUR),
    ]
    stop_losses = [
        StopLossRule(
            symbol="BTC", percentage_threshold=SL_PERCENTAGE,
            trailing=False, sell_percentage=100,
        ),
    ]
    take_profits = [
        TakeProfitRule(
            symbol="BTC", percentage_threshold=TP_PERCENTAGE,
            trailing=False, sell_percentage=100,
        ),
    ]

    @staticmethod
    def _annotate(df):
        df = df.copy()
        df["short_signal"] = df["Close"] == SHORT_ENTRY_PRICE
        df["cover_signal"] = df["Close"] == SHORT_SIGNAL_EXIT_PRICE
        return df

    def generate_signals(self, context, data: Dict[str, Any]):
        df = self._annotate(data["BTC_EUR_OHLCV"])
        yield from signals_from_column(
            df, "short_signal",
            side=SignalSide.OPEN_SHORT, symbol="BTC",
            source="deterministic_short",
        )
        yield from signals_from_column(
            df, "cover_signal",
            side=SignalSide.CLOSE_SHORT, symbol="BTC",
            source="deterministic_short",
        )

    def generate_signal_series(self, data: Dict[str, Any]):
        df = self._annotate(data["BTC_EUR_OHLCV"])
        yield signal_series_from_column(
            df, "short_signal",
            side=SignalSide.OPEN_SHORT, symbol="BTC",
            source="deterministic_short",
        )
        yield signal_series_from_column(
            df, "cover_signal",
            side=SignalSide.CLOSE_SHORT, symbol="BTC",
            source="deterministic_short",
        )


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────

def _create_app(name: str, csv_filename: str):
    app = create_app(name=name, config={RESOURCE_DIRECTORY: _resource_dir()})
    app.add_market(
        market="BITVAVO",
        trading_symbol="EUR",
        initial_balance=INITIAL_BALANCE_EUR,
        fee_percentage=0.0,
        slippage_percentage=0.0,
    )
    app.add_data_provider(
        data_provider=CSVOHLCVDataProvider(
            storage_path=_csv_path(csv_filename),
            symbol="BTC/EUR",
            time_frame="2h",
            market="BITVAVO",
            warmup_window=WARMUP,
        ),
        priority=1,
    )
    return app


def _sorted_trades(run):
    return sorted(run.get_trades(), key=lambda t: t.opened_at)


def _opening_order(trade):
    """Return the entry order (BUY for long, SHORT for short)."""
    is_short = bool(trade.is_short)
    for order in trade.orders:
        side = str(order.order_side).upper()
        if (is_short and side == "SHORT") or (not is_short and side == "BUY"):
            return order
    return trade.orders[0]


def _closing_order(trade):
    """Return the single closing order on a one-shot exit trade."""
    is_short = bool(trade.is_short)
    for order in trade.orders:
        side = str(order.order_side).upper()
        if (is_short and side == "COVER") or (
            not is_short and side == "SELL"
        ):
            return order
    raise AssertionError(f"No closing order on trade {trade.id!r}")


def _run_event_backtest(strategy_cls, csv_filename, start, end, name):
    app = _create_app(name, csv_filename)
    bt = app.run_backtest(
        strategy=strategy_cls(algorithm_id=name),
        backtest_date_range=BacktestDateRange(
            start_date=start, end_date=end,
        ),
        risk_free_rate=0.0,
    )
    return bt.get_all_backtest_runs()[0]


def _run_vector_backtest(strategy_cls, csv_filename, start, end, name):
    app = _create_app(name, csv_filename)
    bt = app.run_vector_backtest(
        strategy=strategy_cls(algorithm_id=name),
        backtest_date_range=BacktestDateRange(
            start_date=start, end_date=end,
        ),
        risk_free_rate=0.0,
        show_progress=False,
    )
    return bt.get_all_backtest_runs()[0]


# ─────────────────────────────────────────────────────────────────────
# Event-mode LONG: full TP / SL / signal-exit coverage
# ─────────────────────────────────────────────────────────────────────

class TestDeterministicLongEventScenario(TestCase):
    """Asserts the event engine produces three trades with exact
    entry / exit prices and signed net-gain values matching closed-form
    arithmetic. Acts as a regression fixture for fill semantics of
    market-style LIMIT entries, TP triggers, SL triggers, and
    manual close signals."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backtest_run = _run_event_backtest(
            DeterministicLongStrategy, LONG_CSV,
            LONG_START, LONG_END, "det_long_evt",
        )
        cls.trades = _sorted_trades(cls.backtest_run)

    # ----- trade count ------------------------------------------------

    def test_three_trades_were_opened_and_closed(self):
        self.assertEqual(3, len(self.trades))
        for t in self.trades:
            self.assertFalse(bool(t.is_short))
            self.assertEqual(str(t.status).upper(), "CLOSED")
            self.assertEqual(LONG_AMOUNT, t.amount)
            self.assertEqual(LONG_ENTRY_PRICE, t.open_price)
            self.assertEqual(LONG_ENTRY_PRICE, _opening_order(t).price)

    # ----- per-trade exit prices -------------------------------------

    def test_first_trade_closes_at_take_profit_price(self):
        trade = self.trades[0]
        self.assertEqual(LONG_TP_PRICE, _closing_order(trade).price)
        # 2 BTC × (150 - 100) = +100 EUR
        self.assertEqual(
            LONG_AMOUNT * (LONG_TP_PRICE - LONG_ENTRY_PRICE),
            trade.net_gain,
        )

    def test_second_trade_closes_at_stop_loss_price(self):
        trade = self.trades[1]
        self.assertEqual(LONG_SL_PRICE, _closing_order(trade).price)
        # 2 BTC × (75 - 100) = -50 EUR
        self.assertEqual(
            LONG_AMOUNT * (LONG_SL_PRICE - LONG_ENTRY_PRICE),
            trade.net_gain,
        )

    def test_third_trade_closes_at_manual_signal_price(self):
        trade = self.trades[2]
        self.assertEqual(
            LONG_SIGNAL_EXIT_PRICE, _closing_order(trade).price,
        )
        # 2 BTC × (90 - 100) = -20 EUR
        self.assertEqual(
            LONG_AMOUNT * (LONG_SIGNAL_EXIT_PRICE - LONG_ENTRY_PRICE),
            trade.net_gain,
        )

    # ----- aggregate P&L ---------------------------------------------

    def test_total_net_gain_matches_arithmetic_sum(self):
        expected = LONG_AMOUNT * (
            (LONG_TP_PRICE - LONG_ENTRY_PRICE)
            + (LONG_SL_PRICE - LONG_ENTRY_PRICE)
            + (LONG_SIGNAL_EXIT_PRICE - LONG_ENTRY_PRICE)
        )
        total = sum(t.net_gain for t in self.trades)
        self.assertAlmostEqual(expected, total, places=6)
        self.assertAlmostEqual(30.0, total, places=6)


# ─────────────────────────────────────────────────────────────────────
# Event-mode LONG with cooldown rule
# ─────────────────────────────────────────────────────────────────────

class TestDeterministicLongEventScenarioWithCooldown(TestCase):
    """Adds a BUY→BUY cooldown of 5 bars. The first BUY (tick 0)
    arms the cooldown which spans the next 4 ticks. The second BUY
    signal lands on tick 4 (Δ = 4 < 5) and is suppressed. The third
    BUY at tick 8 is past the cooldown and proceeds normally, so the
    backtest yields exactly two closed trades: the TP-closed first
    trade and the manually-closed third."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backtest_run = _run_event_backtest(
            DeterministicLongWithCooldownStrategy, LONG_CSV,
            LONG_START, LONG_END, "det_long_evt_cd",
        )
        cls.trades = _sorted_trades(cls.backtest_run)

    def test_cooldown_suppresses_second_entry(self):
        # The SL trade (formerly trade 2) must NOT be produced.
        self.assertEqual(2, len(self.trades))
        exit_prices = [_closing_order(t).price for t in self.trades]
        self.assertEqual(
            [LONG_TP_PRICE, LONG_SIGNAL_EXIT_PRICE], exit_prices,
        )

    def test_total_net_gain_excludes_blocked_trade(self):
        expected = LONG_AMOUNT * (
            (LONG_TP_PRICE - LONG_ENTRY_PRICE)            # +100
            + (LONG_SIGNAL_EXIT_PRICE - LONG_ENTRY_PRICE)  # -20
        )
        total = sum(t.net_gain for t in self.trades)
        self.assertAlmostEqual(expected, total, places=6)
        self.assertAlmostEqual(80.0, total, places=6)


# ─────────────────────────────────────────────────────────────────────
# Event-mode LONG with cooldown armed by TP fills
# ─────────────────────────────────────────────────────────────────────

class TestDeterministicLongEventScenarioWithSellCooldown(TestCase):
    """Regression for cooldowns being armed by system-emitted exits.

    Without :class:`RecordCooldownPhase._record_system_exits`, a TP /
    SL fill bypasses the strategy phase pipeline and never reaches
    the :class:`CooldownTracker`. With that scan in place the SELL
    LIMIT order produced by the TP rule records into the tracker, so
    a ``CooldownRule(trigger=SELL, blocks=BUY, bars=4)`` does block
    the next BUY four ticks later. The backtest must therefore yield
    exactly two trades (TP-closed first trade + manually-closed third
    trade)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backtest_run = _run_event_backtest(
            DeterministicLongWithSellCooldownStrategy, LONG_CSV,
            LONG_START, LONG_END, "det_long_evt_sell_cd",
        )
        cls.trades = _sorted_trades(cls.backtest_run)

    def test_tp_fill_arms_cooldown_and_suppresses_second_entry(self):
        self.assertEqual(2, len(self.trades))
        exit_prices = [_closing_order(t).price for t in self.trades]
        self.assertEqual(
            [LONG_TP_PRICE, LONG_SIGNAL_EXIT_PRICE], exit_prices,
        )

    def test_total_net_gain_excludes_blocked_sl_trade(self):
        expected = LONG_AMOUNT * (
            (LONG_TP_PRICE - LONG_ENTRY_PRICE)            # +100
            + (LONG_SIGNAL_EXIT_PRICE - LONG_ENTRY_PRICE)  # -20
        )
        total = sum(t.net_gain for t in self.trades)
        self.assertAlmostEqual(expected, total, places=6)
        self.assertAlmostEqual(80.0, total, places=6)


# ─────────────────────────────────────────────────────────────────────
# Vector-mode LONG — mirrors the event LONG scenario (#487)
# ─────────────────────────────────────────────────────────────────────

class TestDeterministicLongVectorScenario(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backtest_run = _run_vector_backtest(
            DeterministicLongStrategy, LONG_CSV,
            LONG_START, LONG_END, "det_long_vec",
        )
        cls.trades = _sorted_trades(cls.backtest_run)

    def test_three_trades_were_opened_and_closed(self):
        self.assertEqual(3, len(self.trades))
        for t in self.trades:
            self.assertFalse(bool(t.is_short))
            self.assertEqual(str(t.status).upper(), "CLOSED")
            self.assertEqual(LONG_AMOUNT, t.amount)
            self.assertEqual(LONG_ENTRY_PRICE, t.open_price)

    def test_first_trade_closes_at_take_profit_price(self):
        trade = self.trades[0]
        self.assertAlmostEqual(
            LONG_AMOUNT * (LONG_TP_PRICE - LONG_ENTRY_PRICE),
            trade.net_gain, places=6,
        )

    def test_second_trade_closes_at_stop_loss_price(self):
        trade = self.trades[1]
        self.assertAlmostEqual(
            LONG_AMOUNT * (LONG_SL_PRICE - LONG_ENTRY_PRICE),
            trade.net_gain, places=6,
        )

    def test_third_trade_closes_at_manual_signal_price(self):
        trade = self.trades[2]
        self.assertAlmostEqual(
            LONG_AMOUNT * (LONG_SIGNAL_EXIT_PRICE - LONG_ENTRY_PRICE),
            trade.net_gain, places=6,
        )

    def test_total_net_gain_matches_arithmetic_sum(self):
        total = sum(t.net_gain for t in self.trades)
        self.assertAlmostEqual(30.0, total, places=6)


# ─────────────────────────────────────────────────────────────────────
# Event-mode SHORT — mirror of the LONG scenario
# ─────────────────────────────────────────────────────────────────────

class TestDeterministicShortEventScenario(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backtest_run = _run_event_backtest(
            DeterministicShortStrategy, SHORT_CSV,
            SHORT_START, SHORT_END, "det_short_evt",
        )
        cls.trades = _sorted_trades(cls.backtest_run)

    def test_three_short_trades_were_opened_and_closed(self):
        self.assertEqual(3, len(self.trades))
        for t in self.trades:
            self.assertTrue(bool(t.is_short))
            self.assertEqual(str(t.status).upper(), "CLOSED")
            self.assertEqual(SHORT_AMOUNT, t.amount)
            self.assertEqual(SHORT_ENTRY_PRICE, t.open_price)

    def test_first_short_closes_at_take_profit_price(self):
        trade = self.trades[0]
        self.assertEqual(SHORT_TP_PRICE, _closing_order(trade).price)
        # 2 BTC × (100 - 50) = +100 EUR
        self.assertEqual(
            SHORT_AMOUNT * (SHORT_ENTRY_PRICE - SHORT_TP_PRICE),
            trade.net_gain,
        )

    def test_second_short_closes_at_stop_loss_price(self):
        trade = self.trades[1]
        self.assertEqual(SHORT_SL_PRICE, _closing_order(trade).price)
        # 2 BTC × (100 - 125) = -50 EUR
        self.assertEqual(
            SHORT_AMOUNT * (SHORT_ENTRY_PRICE - SHORT_SL_PRICE),
            trade.net_gain,
        )

    def test_third_short_closes_at_manual_signal_price(self):
        trade = self.trades[2]
        self.assertEqual(
            SHORT_SIGNAL_EXIT_PRICE, _closing_order(trade).price,
        )
        # 2 BTC × (100 - 110) = -20 EUR
        self.assertEqual(
            SHORT_AMOUNT * (SHORT_ENTRY_PRICE - SHORT_SIGNAL_EXIT_PRICE),
            trade.net_gain,
        )

    def test_total_net_gain_matches_arithmetic_sum(self):
        expected = SHORT_AMOUNT * (
            (SHORT_ENTRY_PRICE - SHORT_TP_PRICE)
            + (SHORT_ENTRY_PRICE - SHORT_SL_PRICE)
            + (SHORT_ENTRY_PRICE - SHORT_SIGNAL_EXIT_PRICE)
        )
        total = sum(t.net_gain for t in self.trades)
        self.assertAlmostEqual(expected, total, places=6)
        self.assertAlmostEqual(30.0, total, places=6)


# ─────────────────────────────────────────────────────────────────────
# Vector-mode SHORT — mirrors the event SHORT scenario (#433 + #487)
# ─────────────────────────────────────────────────────────────────────

class TestDeterministicShortVectorScenario(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.backtest_run = _run_vector_backtest(
            DeterministicShortStrategy, SHORT_CSV,
            SHORT_START, SHORT_END, "det_short_vec",
        )
        cls.trades = _sorted_trades(cls.backtest_run)

    def test_three_short_trades_were_opened_and_closed(self):
        self.assertEqual(3, len(self.trades))
        for t in self.trades:
            self.assertTrue(bool(t.is_short))
            self.assertEqual(str(t.status).upper(), "CLOSED")
            self.assertEqual(SHORT_AMOUNT, t.amount)
            self.assertEqual(SHORT_ENTRY_PRICE, t.open_price)

    def test_first_short_closes_at_take_profit_price(self):
        trade = self.trades[0]
        self.assertAlmostEqual(
            SHORT_AMOUNT * (SHORT_ENTRY_PRICE - SHORT_TP_PRICE),
            trade.net_gain, places=6,
        )

    def test_second_short_closes_at_stop_loss_price(self):
        trade = self.trades[1]
        self.assertAlmostEqual(
            SHORT_AMOUNT * (SHORT_ENTRY_PRICE - SHORT_SL_PRICE),
            trade.net_gain, places=6,
        )

    def test_third_short_closes_at_manual_signal_price(self):
        trade = self.trades[2]
        self.assertAlmostEqual(
            SHORT_AMOUNT * (
                SHORT_ENTRY_PRICE - SHORT_SIGNAL_EXIT_PRICE
            ),
            trade.net_gain, places=6,
        )

    def test_total_net_gain_matches_arithmetic_sum(self):
        total = sum(t.net_gain for t in self.trades)
        self.assertAlmostEqual(30.0, total, places=6)


if __name__ == "__main__":
    unittest.main()
