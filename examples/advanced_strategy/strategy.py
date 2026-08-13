"""
Advanced multi-signal trading strategy.

A single strategy class that showcases most of the framework's
building blocks at once:

- **Long *and* short signal generation** in one strategy: trend
  following longs via an EMA(20)/EMA(50) crossover, mean-reversion
  shorts via RSI(14) overbought/oversold.
- **Both engines, one strategy**: implements `generate_signal_series`
  (vector backtest) *and* `generate_signals` (event-driven backtest /
  paper / live) from the same indicator columns, so it runs unmodified
  in either engine.
- **Risk management building blocks**: a trailing stop loss and a
  fixed take profit, attached declaratively via `stop_losses` /
  `take_profits`.
- **Trade lifecycle hooks** (`on_trade_opened`, `on_trade_closed`,
  `on_trade_stop_loss_triggered`, ...) for observability, independent
  of the signal-generation code.
- **`scheduled_functions`**: a daily exposure report that runs on its
  own cadence, decoupled from the strategy's 2h main tick.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable

import pandas as pd
from pyindicators import crossover, crossunder, ema, rsi

from investing_algorithm_framework import (
    ConflictPolicy,
    ConflictResolution,
    DataSource,
    DataType,
    PositionSize,
    Schedule,
    ScheduledFunction,
    Signal,
    SignalSeries,
    SignalSide,
    StopLossRule,
    TakeProfitRule,
    TimeUnit,
    TradingStrategy,
    signal_series_from_column,
    signals_from_column,
)

SYMBOL = "BTC"
MARKET = "BITVAVO"
DATA_SOURCE_ID = "BTC_EUR_OHLCV"


class AdvancedMultiSignalStrategy(TradingStrategy):
    """Trend-following longs + mean-reversion shorts on BTC/EUR, with
    trailing risk management and a daily exposure report."""

    algorithm_id = "advanced-multi-signal"
    schedule = Schedule.every(2, TimeUnit.HOUR)
    symbols = [SYMBOL]

    # The trend (long) and mean-reversion (short) signals can fire on
    # the same bar; PRIORITY breaks the tie deterministically instead
    # of raising (the framework's default is to raise on same-symbol
    # opposing-direction conflicts).
    conflict_policy = ConflictPolicy.default().evolve(
        on_conflict=ConflictResolution.PRIORITY
    )

    position_sizes = [
        PositionSize(symbol=SYMBOL, percentage_of_portfolio=10.0),
    ]
    stop_losses = [
        StopLossRule(
            symbol=SYMBOL, percentage_threshold=5,
            sell_percentage=100, trailing=True,
        ),
    ]
    take_profits = [
        TakeProfitRule(
            symbol=SYMBOL, percentage_threshold=8,
            sell_percentage=100, trailing=False,
        ),
    ]
    # Fires once a day, independent of the 2h main tick above.
    scheduled_functions = [
        ScheduledFunction(
            func="log_daily_exposure",
            schedule=Schedule.every(24, TimeUnit.HOUR),
        ),
    ]
    data_sources = [
        DataSource(
            identifier=DATA_SOURCE_ID,
            data_type=DataType.OHLCV,
            market=MARKET,
            symbol="BTC/EUR",
            time_frame="2h",
            warmup_window=60,
            pandas=True,
        ),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # In-memory log strategies can use for their own observability;
        # a real strategy might push these to a metrics/alerting system.
        self.trade_log = []

    @staticmethod
    def _with_indicators(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = ema(df, period=20, source_column="Close",
                  result_column="ema_fast")
        df = ema(df, period=50, source_column="Close",
                  result_column="ema_slow")
        df = crossover(df, first_column="ema_fast",
                        second_column="ema_slow",
                        result_column="ema_bull_cross")
        df = crossunder(df, first_column="ema_fast",
                         second_column="ema_slow",
                         result_column="ema_bear_cross")
        df = rsi(df, period=14, source_column="Close",
                  result_column="rsi_14")
        df["rsi_overbought"] = df["rsi_14"] > 75
        df["rsi_reverted"] = df["rsi_14"] < 50
        return df

    def generate_signal_series(
        self, data: Dict[str, Any]
    ) -> Iterable[SignalSeries]:
        df = self._with_indicators(data[DATA_SOURCE_ID])
        yield signal_series_from_column(
            df, "ema_bull_cross", side=SignalSide.OPEN_LONG,
            symbol=SYMBOL, source="ema_cross",
        )
        yield signal_series_from_column(
            df, "ema_bear_cross", side=SignalSide.CLOSE_LONG,
            symbol=SYMBOL, source="ema_cross",
        )
        yield signal_series_from_column(
            df, "rsi_overbought", side=SignalSide.OPEN_SHORT,
            symbol=SYMBOL, source="rsi_reversion",
        )
        yield signal_series_from_column(
            df, "rsi_reverted", side=SignalSide.CLOSE_SHORT,
            symbol=SYMBOL, source="rsi_reversion",
        )

    def generate_signals(
        self, context, data: Dict[str, Any]
    ) -> Iterable[Signal]:
        df = self._with_indicators(data[DATA_SOURCE_ID])
        yield from signals_from_column(
            df, "ema_bull_cross", side=SignalSide.OPEN_LONG,
            symbol=SYMBOL, source="ema_cross",
        )
        yield from signals_from_column(
            df, "ema_bear_cross", side=SignalSide.CLOSE_LONG,
            symbol=SYMBOL, source="ema_cross",
        )
        yield from signals_from_column(
            df, "rsi_overbought", side=SignalSide.OPEN_SHORT,
            symbol=SYMBOL, source="rsi_reversion",
        )
        yield from signals_from_column(
            df, "rsi_reverted", side=SignalSide.CLOSE_SHORT,
            symbol=SYMBOL, source="rsi_reversion",
        )

    # ------------------------------------------------------------------ #
    # Trade lifecycle hooks - observability, decoupled from signals      #
    # ------------------------------------------------------------------ #

    def on_trade_opened(self, context, trade):
        side = "SHORT" if trade.is_short else "LONG"
        self.trade_log.append(
            f"OPENED {side} {trade.symbol} @ {trade.open_price}"
        )

    def on_trade_closed(self, context, trade):
        self.trade_log.append(
            f"CLOSED {trade.symbol} net_gain={trade.net_gain:.2f}"
        )

    def on_trade_stop_loss_triggered(self, context, trade):
        self.trade_log.append(f"STOP LOSS hit for {trade.symbol}")

    def on_trade_trailing_stop_loss_triggered(self, context, trade):
        self.trade_log.append(f"TRAILING STOP LOSS hit for {trade.symbol}")

    def on_trade_take_profit_triggered(self, context, trade):
        self.trade_log.append(f"TAKE PROFIT hit for {trade.symbol}")

    # ------------------------------------------------------------------ #
    # scheduled_functions - own cadence, separate from the main tick     #
    # ------------------------------------------------------------------ #

    def log_daily_exposure(self, context, data):
        open_trades = [
            t for t in context.get_trades() if t.status == "OPEN"
        ]
        exposure = sum(t.cost for t in open_trades)
        self.trade_log.append(
            f"[daily] {len(open_trades)} open trade(s), "
            f"exposure={exposure:.2f}"
        )
