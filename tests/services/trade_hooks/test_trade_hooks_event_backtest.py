"""End-to-end test that `TradingStrategy.on_trade_*` hooks actually
fire, at the right point, during a real event-driven backtest.

`tests/services/trade_hooks/test_trade_hook_dispatcher.py` only
exercises `TradeHookDispatcher` in isolation (hand-built strategies and
plain trade stand-ins passed straight to `dispatch()`). Nothing
verified the real wiring — `TradeService`/`TradeOrderEvaluator`
dispatching through the real `EventLoopService`-configured singleton
during an actual order fill / trade lifecycle transition. This file
closes that gap.

Per `TradeHookDispatcher`'s own docstring, these hooks are dispatched
in live trading and event-driven backtests only — the vector engine
has no per-trade callback point, so this is deliberately event-driven
only (`app.run_backtest`), not compared against the vector engine.
"""
from datetime import datetime, timezone
from pathlib import Path
from unittest import TestCase

from investing_algorithm_framework import TradingStrategy, DataSource, \
    TimeUnit, DataType, create_app, BacktestDateRange, PositionSize, \
    RESOURCE_DIRECTORY, CSVOHLCVDataProvider, Schedule, SignalSide, \
    signals_from_column, StopLossRule, TakeProfitRule, Study, Universe, \
    BacktestWindow, BacktestEngine

CSV_FILENAME = "OHLCV_BTC-EUR_BITVAVO_2h_RISK_RULE_HOOKS.csv"
WARMUP = 5

# Buy at Close=105 (10:00), price rises 105->108->150->200->250, then
# crashes to 100 (well below the trailing 5% stop at 250*0.95=237.5).
SL_START_DATE = datetime(2020, 12, 20, 10, 0, 0, tzinfo=timezone.utc)
SL_END_DATE = datetime(2020, 12, 21, 0, 0, 0, tzinfo=timezone.utc)

# Same buy, but the window ends right after price clears the fixed
# 10% take-profit threshold (105 * 1.10 = 115.5) at Close=150 (14:00).
TP_START_DATE = datetime(2020, 12, 20, 10, 0, 0, tzinfo=timezone.utc)
TP_END_DATE = datetime(2020, 12, 20, 16, 0, 0, tzinfo=timezone.utc)


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


class _HookRecordingMixin:
    """Records every `on_trade_*` hook invocation, in call order, as
    `(hook_name, trade_id)` tuples on `self.hook_calls`."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hook_calls = []

    def _record(self, hook_name, trade):
        self.hook_calls.append((hook_name, getattr(trade, "id", None)))

    def on_trade_created(self, context, trade):
        self._record("on_trade_created", trade)

    def on_trade_opened(self, context, trade):
        self._record("on_trade_opened", trade)

    def on_trade_closed(self, context, trade):
        self._record("on_trade_closed", trade)

    def on_trade_updated(self, context, trade):
        self._record("on_trade_updated", trade)

    def on_trade_stop_loss_triggered(self, context, trade):
        self._record("on_trade_stop_loss_triggered", trade)

    def on_trade_trailing_stop_loss_triggered(self, context, trade):
        self._record("on_trade_trailing_stop_loss_triggered", trade)

    def on_trade_take_profit_triggered(self, context, trade):
        self._record("on_trade_take_profit_triggered", trade)

    def on_trade_stop_loss_created(self, context, trade):
        self._record("on_trade_stop_loss_created", trade)

    def on_trade_trailing_stop_loss_created(self, context, trade):
        self._record("on_trade_trailing_stop_loss_created", trade)

    def on_trade_take_profit_created(self, context, trade):
        self._record("on_trade_take_profit_created", trade)

    def on_trade_stop_loss_updated(self, context, trade):
        self._record("on_trade_stop_loss_updated", trade)

    def on_trade_trailing_stop_loss_updated(self, context, trade):
        self._record("on_trade_trailing_stop_loss_updated", trade)

    def on_trade_take_profit_updated(self, context, trade):
        self._record("on_trade_take_profit_updated", trade)


class TrailingStopLossHookStrategy(_HookRecordingMixin, TradingStrategy):
    """Opens one long at Close == 105, protected by a 5% trailing
    stop loss."""
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]
    stop_losses = [
        StopLossRule(
            symbol="BTC", percentage_threshold=5,
            sell_percentage=100, trailing=True,
        ),
    ]

    def generate_signals(self, context, data):
        df = data["BTC_EUR_OHLCV"].copy()
        df["buy"] = df["Close"] == 105
        yield from signals_from_column(
            df, "buy", side=SignalSide.OPEN_LONG, symbol="BTC",
        )


class TakeProfitHookStrategy(_HookRecordingMixin, TradingStrategy):
    """Opens one long at Close == 105, protected by a fixed (non
    trailing) 10% take profit."""
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = ["BTC"]
    data_sources = [_make_data_source()]
    position_sizes = [
        PositionSize(symbol="BTC", percentage_of_portfolio=20.0),
    ]
    take_profits = [
        TakeProfitRule(
            symbol="BTC", percentage_threshold=10,
            sell_percentage=100, trailing=False,
        ),
    ]

    def generate_signals(self, context, data):
        df = data["BTC_EUR_OHLCV"].copy()
        df["buy"] = df["Close"] == 105
        yield from signals_from_column(
            df, "buy", side=SignalSide.OPEN_LONG, symbol="BTC",
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


class TestTrailingStopLossHooks(TestCase):
    """Buy -> rally -> crash: exercises the full stop-loss hook set."""

    @classmethod
    def setUpClass(cls):
        cls.strategy = TrailingStopLossHookStrategy(
            algorithm_id="trailing_sl_hooks"
        )
        app = _create_app("TrailingStopLossHooksTest")
        date_range = BacktestDateRange(
            start_date=SL_START_DATE, end_date=SL_END_DATE
        )
        backtests = app.run_backtest(
            strategy=cls.strategy,
            study=Study(
                universe=Universe(market="BITVAVO", trading_symbol="EUR"),
                risk_free_rate=0.027,
                backtest_windows=[BacktestWindow(train_range=date_range)],
                engines=[BacktestEngine.EVENT_DRIVEN],
            ),
        )
        cls.backtest_run = backtests[0].get_all_backtest_runs()[0]

    def test_one_trade_was_opened_and_closed(self):
        trades = self.backtest_run.get_trades()
        self.assertEqual(1, len(trades))
        self.assertEqual("CLOSED", trades[0].status)

    def test_creation_and_open_hooks_fired(self):
        names = [name for name, _ in self.strategy.hook_calls]
        self.assertEqual(1, names.count("on_trade_created"))
        self.assertEqual(1, names.count("on_trade_opened"))
        self.assertLess(
            names.index("on_trade_created"),
            names.index("on_trade_opened"),
        )

    def test_stop_loss_created_hooks_fired_both_variants(self):
        """A trailing stop loss dispatches the plain *and* the
        trailing-specific "created" hook."""
        names = [name for name, _ in self.strategy.hook_calls]
        self.assertEqual(1, names.count("on_trade_stop_loss_created"))
        self.assertEqual(
            1, names.count("on_trade_trailing_stop_loss_created")
        )
        self.assertLess(
            names.index("on_trade_stop_loss_created"),
            names.index("on_trade_trailing_stop_loss_created"),
        )

    def test_trailing_stop_loss_updated_fires_in_backtest(self):
        """`BacktestTradeOrderEvaluator.evaluate()` routes each open
        trade's price update through `TradeService.update(trade_id,
        ...)` (not a direct `Trade.update()` + bulk
        `trade_service.save_all(...)`), which is what compares the
        stop loss's before/after price and dispatches
        `on_trade_(trailing_)stop_loss_updated`. As the trailing stop
        level advances across the rally (the persisted
        `TradeStopLoss.high_water_mark` moves from 105 to 250), the
        "updated" hook fires once per bar where the level actually
        moves, and only the trailing-specific variant is dispatched
        (never the plain `on_trade_stop_loss_updated`, since this
        rule is trailing)."""
        names = [name for name, _ in self.strategy.hook_calls]
        self.assertGreater(
            names.count("on_trade_trailing_stop_loss_updated"), 0
        )
        self.assertEqual(0, names.count("on_trade_stop_loss_updated"))

    def test_trailing_stop_loss_triggered_not_plain_stop_loss(self):
        """A trailing rule dispatches the trailing-specific triggered
        hook, never the plain one."""
        names = [name for name, _ in self.strategy.hook_calls]
        self.assertEqual(
            1, names.count("on_trade_trailing_stop_loss_triggered")
        )
        self.assertEqual(0, names.count("on_trade_stop_loss_triggered"))

    def test_closed_hook_fires_after_trigger_not_updated(self):
        """A 100%-closing trigger dispatches `on_trade_closed`; a
        trade can't be both fully closed and merely "updated" from the
        same fill, so `on_trade_updated` should NOT also fire here (it
        is reserved for partial-close fills that leave the trade
        open). Note: `on_trade_closed` actually fires *before* the
        trailing_stop_loss_triggered dispatch — `_create_order` (which
        synchronously fills the closing SELL order) runs before
        `_check_stop_losses` gets to notifying the strategy."""
        names = [name for name, _ in self.strategy.hook_calls]
        self.assertEqual(1, names.count("on_trade_closed"))
        self.assertEqual(0, names.count("on_trade_updated"))
        triggered_idx = names.index(
            "on_trade_trailing_stop_loss_triggered"
        )
        self.assertGreater(triggered_idx, names.index("on_trade_closed"))

    def test_all_hooks_reference_the_same_trade(self):
        trade_ids = {
            trade_id for _, trade_id in self.strategy.hook_calls
        }
        self.assertEqual(1, len(trade_ids))


class TestTakeProfitHooks(TestCase):
    """Buy -> price clears a fixed take-profit threshold."""

    @classmethod
    def setUpClass(cls):
        cls.strategy = TakeProfitHookStrategy(
            algorithm_id="take_profit_hooks"
        )
        app = _create_app("TakeProfitHooksTest")
        date_range = BacktestDateRange(
            start_date=TP_START_DATE, end_date=TP_END_DATE
        )
        backtests = app.run_backtest(
            strategy=cls.strategy,
            study=Study(
                universe=Universe(market="BITVAVO", trading_symbol="EUR"),
                risk_free_rate=0.027,
                backtest_windows=[BacktestWindow(train_range=date_range)],
                engines=[BacktestEngine.EVENT_DRIVEN],
            ),
        )
        cls.backtest_run = backtests[0].get_all_backtest_runs()[0]

    def test_one_trade_was_opened_and_closed(self):
        trades = self.backtest_run.get_trades()
        self.assertEqual(1, len(trades))
        self.assertEqual("CLOSED", trades[0].status)

    def test_take_profit_created_and_triggered_hooks_fired(self):
        names = [name for name, _ in self.strategy.hook_calls]
        self.assertEqual(1, names.count("on_trade_take_profit_created"))
        self.assertEqual(
            1, names.count("on_trade_take_profit_triggered")
        )
        self.assertLess(
            names.index("on_trade_take_profit_created"),
            names.index("on_trade_take_profit_triggered"),
        )

    def test_take_profit_updated_never_fires_for_fixed_rule(self):
        """Only a *trailing* take profit ever changes its trigger
        price (and thus fires the "updated" hook) — a fixed take
        profit's price never moves after creation."""
        names = [name for name, _ in self.strategy.hook_calls]
        self.assertEqual(0, names.count("on_trade_take_profit_updated"))

    def test_closed_hook_fires_after_trigger_not_updated(self):
        """A 100%-closing trigger dispatches `on_trade_closed`, not
        `on_trade_updated` (reserved for partial-close fills that
        leave the trade open — see `TradeService.
        _create_trade_allocations_explicit`'s if/else). Note:
        `on_trade_closed` fires *before* the triggered dispatch — see
        the trailing stop loss test for why."""
        names = [name for name, _ in self.strategy.hook_calls]
        self.assertEqual(1, names.count("on_trade_closed"))
        self.assertEqual(0, names.count("on_trade_updated"))
        triggered_idx = names.index("on_trade_take_profit_triggered")
        self.assertGreater(triggered_idx, names.index("on_trade_closed"))
