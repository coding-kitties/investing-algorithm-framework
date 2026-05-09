"""Donchian-style volatility breakout (event-driven)."""
from __future__ import annotations

from typing import Any, Dict

from investing_algorithm_framework import (
    Context,
    DataSource,
    DataType,
    OrderSide,
    OrderType,
    TimeUnit,
    TradingStrategy,
)

SYMBOL = "BTC/EUR"
WINDOW = 48


class VolatilityBreakoutStrategy(TradingStrategy):
    algorithm_id = "vol-breakout-event-driven"
    time_unit = TimeUnit.HOUR
    interval = 1
    market = "BITVAVO"
    trading_symbol = "EUR"
    symbols = [SYMBOL.split("/")[0]]

    data_sources = [
        DataSource(
            identifier=f"{SYMBOL}-ohlcv",
            data_type=DataType.OHLCV, market=market, symbol=SYMBOL,
            time_frame="1h", warmup_window=WINDOW + 5, pandas=True,
        )
    ]

    def run_strategy(self, context: Context, data: Dict[str, Any]) -> None:
        df = data[f"{SYMBOL}-ohlcv"]
        if len(df) < WINDOW + 1:
            return

        recent = df.tail(WINDOW + 1)
        prior = recent.iloc[:-1]
        last_close = float(recent["Close"].iloc[-1])
        rolling_high = float(prior["High"].max())
        rolling_low = float(prior["Low"].min())

        sym = self.symbols[0]
        held = context.has_position(sym, market=self.market)

        if not held and last_close > rolling_high:
            cash = context.get_unallocated()
            if cash <= 0:
                return
            amount = (cash * 0.995) / last_close
            context.create_order(
                target_symbol=sym, order_side=OrderSide.BUY,
                order_type=OrderType.LIMIT, price=last_close, amount=amount,
            )
        elif held and last_close < rolling_low:
            pos = context.get_position(sym, market=self.market)
            context.create_order(
                target_symbol=sym, order_side=OrderSide.SELL,
                order_type=OrderType.LIMIT, price=last_close,
                amount=pos.get_amount(),
            )
