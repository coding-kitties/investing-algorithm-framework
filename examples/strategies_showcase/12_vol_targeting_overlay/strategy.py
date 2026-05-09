"""Volatility-targeted long-BTC overlay."""
from __future__ import annotations

import math
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
LOOKBACK = 30
TARGET_ANNUAL_VOL = 0.25  # 25% annualised
REBALANCE_EVERY_BARS = 7  # weekly
W_MAX = 1.0


class VolTargetStrategy(TradingStrategy):
    algorithm_id = "vol-targeting-overlay"
    time_unit = TimeUnit.DAY
    interval = 1
    market = "BITVAVO"
    trading_symbol = "EUR"
    symbols = [SYMBOL.split("/")[0]]

    data_sources = [
        DataSource(
            identifier=f"{SYMBOL}-ohlcv",
            data_type=DataType.OHLCV, market=market, symbol=SYMBOL,
            time_frame="1d", warmup_window=LOOKBACK + 5, pandas=True,
        )
    ]

    def __init__(self):
        super().__init__()
        self._bar_count = 0

    def run_strategy(self, context: Context, data: Dict[str, Any]) -> None:
        self._bar_count += 1
        if self._bar_count % REBALANCE_EVERY_BARS != 1:
            return

        df = data[f"{SYMBOL}-ohlcv"]
        if len(df) < LOOKBACK + 1:
            return

        rets = df["Close"].pct_change().tail(LOOKBACK).dropna()
        sd_daily = float(rets.std())
        if sd_daily <= 0 or math.isnan(sd_daily):
            return
        sd_annual = sd_daily * math.sqrt(365)
        target_w = min(TARGET_ANNUAL_VOL / sd_annual, W_MAX)

        sym = self.symbols[0]
        price = float(df["Close"].iloc[-1])
        equity = context.get_unallocated()
        if context.has_position(sym, market=self.market):
            equity += context.get_position(
                sym, market=self.market
            ).get_amount() * price

        target_amount = (equity * target_w) / price
        current = 0.0
        if context.has_position(sym, market=self.market):
            current = context.get_position(
                sym, market=self.market
            ).get_amount()
        delta = target_amount - current
        if abs(delta * price) < 5:
            return
        side = OrderSide.BUY if delta > 0 else OrderSide.SELL
        context.create_order(
            target_symbol=sym, order_side=side,
            order_type=OrderType.LIMIT, price=price, amount=abs(delta),
        )
