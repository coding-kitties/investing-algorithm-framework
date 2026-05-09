"""Slow market-making: post buy-below-mid, sell-above-mid every bar."""
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
SPREAD_BPS = 25.0       # quote ±25 bps around mid
QUOTE_SIZE_EUR = 50.0
INVENTORY_CAP_EUR = 250.0


class SlowMarketMakingStrategy(TradingStrategy):
    algorithm_id = "slow-market-making"
    time_unit = TimeUnit.HOUR
    interval = 1
    market = "BITVAVO"
    trading_symbol = "EUR"
    symbols = [SYMBOL.split("/")[0]]

    data_sources = [
        DataSource(
            identifier=f"{SYMBOL}-ohlcv",
            data_type=DataType.OHLCV, market=market, symbol=SYMBOL,
            time_frame="1h", warmup_window=2, pandas=True,
        )
    ]

    def run_strategy(self, context: Context, data: Dict[str, Any]) -> None:
        df = data[f"{SYMBOL}-ohlcv"]
        if len(df) == 0:
            return
        mid = float(df["Close"].iloc[-1])
        if mid <= 0:
            return

        bid = mid * (1.0 - SPREAD_BPS / 10_000.0)
        ask = mid * (1.0 + SPREAD_BPS / 10_000.0)
        sym = self.symbols[0]

        # Inventory-cap-aware buy quote.
        held_value = 0.0
        if context.has_position(sym, market=self.market):
            held_value = context.get_position(
                sym, market=self.market
            ).get_amount() * mid

        if held_value < INVENTORY_CAP_EUR \
                and context.get_unallocated() >= QUOTE_SIZE_EUR:
            buy_amt = (QUOTE_SIZE_EUR * 0.995) / bid
            context.create_order(
                target_symbol=sym, order_side=OrderSide.BUY,
                order_type=OrderType.LIMIT, price=bid, amount=buy_amt,
            )

        # Sell quote: only if we have inventory to offload.
        if context.has_position(sym, market=self.market):
            pos_amt = context.get_position(
                sym, market=self.market
            ).get_amount()
            sell_amt = min(pos_amt, (QUOTE_SIZE_EUR * 0.995) / ask)
            if sell_amt > 0:
                context.create_order(
                    target_symbol=sym, order_side=OrderSide.SELL,
                    order_type=OrderType.LIMIT, price=ask, amount=sell_amt,
                )
