"""Donchian-style volatility breakout (event-driven)."""
from __future__ import annotations

from typing import Any, Dict, Iterable

from investing_algorithm_framework import (
    Context,
    DataSource,
    DataType,
    PositionSize,
    Signal,
    SignalSide,
    TimeUnit,
    TradingStrategy,
    Schedule,
)

SYMBOL = "BTC/EUR"
BASE = SYMBOL.split("/")[0]
WINDOW = 48


class VolatilityBreakoutStrategy(TradingStrategy):
    algorithm_id = "vol-breakout-event-driven"
    schedule = Schedule.every(1, TimeUnit.HOUR)
    market = "BITVAVO"
    symbols = [BASE]

    data_sources = [
        DataSource(
            identifier=f"{SYMBOL}-ohlcv",
            data_type=DataType.OHLCV, market=market, symbol=SYMBOL,
            time_frame="1h", warmup_window=WINDOW + 5, pandas=True,
        )
    ]

    position_sizes = [
        PositionSize(symbol=BASE, percentage_of_portfolio=99.0),
    ]

    def generate_signals(
        self, context: Context, data: Dict[str, Any]
    ) -> Iterable[Signal]:
        df = data[f"{SYMBOL}-ohlcv"]
        if len(df) < WINDOW + 1:
            return

        recent = df.tail(WINDOW + 1)
        prior = recent.iloc[:-1]
        last_close = float(recent["Close"].iloc[-1])
        rolling_high = float(prior["High"].max())
        rolling_low = float(prior["Low"].min())

        held = context.has_position(BASE, market=self.market)

        if not held and last_close > rolling_high:
            yield Signal(
                symbol=BASE, side=SignalSide.OPEN_LONG, source="breakout",
            )
        elif held and last_close < rolling_low:
            yield Signal(
                symbol=BASE, side=SignalSide.CLOSE_LONG, source="breakout",
            )
