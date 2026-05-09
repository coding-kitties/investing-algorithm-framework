"""Pairs trading (long-only, spot-friendly variant)."""
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

SYMBOL_A = "BTC/EUR"
SYMBOL_B = "ETH/EUR"
WINDOW = 60
Z_ENTRY = 1.5
Z_EXIT = 0.3


class PairsTradingStrategy(TradingStrategy):
    algorithm_id = "pairs-trading-zscore"
    time_unit = TimeUnit.DAY
    interval = 1
    market = "BITVAVO"
    trading_symbol = "EUR"
    symbols = [SYMBOL_A.split("/")[0], SYMBOL_B.split("/")[0]]

    data_sources = [
        DataSource(
            identifier=f"{SYMBOL_A}-ohlcv",
            data_type=DataType.OHLCV, market=market, symbol=SYMBOL_A,
            time_frame="1d", warmup_window=WINDOW + 5, pandas=True,
        ),
        DataSource(
            identifier=f"{SYMBOL_B}-ohlcv",
            data_type=DataType.OHLCV, market=market, symbol=SYMBOL_B,
            time_frame="1d", warmup_window=WINDOW + 5, pandas=True,
        ),
    ]

    def run_strategy(self, context: Context, data: Dict[str, Any]) -> None:
        df_a = data[f"{SYMBOL_A}-ohlcv"]
        df_b = data[f"{SYMBOL_B}-ohlcv"]
        if len(df_a) < WINDOW + 1 or len(df_b) < WINDOW + 1:
            return

        # log spread with hedge ratio β = 1 (simplest variant)
        spread = (df_a["Close"].apply(math.log)
                  - df_b["Close"].apply(math.log)).tail(WINDOW + 1)
        mu = spread.iloc[:-1].mean()
        sd = spread.iloc[:-1].std()
        if sd == 0 or math.isnan(sd):
            return
        z = (spread.iloc[-1] - mu) / sd

        base_a = SYMBOL_A.split("/")[0]
        base_b = SYMBOL_B.split("/")[0]
        price_a = float(df_a["Close"].iloc[-1])
        price_b = float(df_b["Close"].iloc[-1])
        has_a = context.has_position(base_a, market=self.market)
        has_b = context.has_position(base_b, market=self.market)

        # ENTRY: long the *cheap* leg.
        if z > Z_ENTRY and not has_b:
            self._close_if_held(context, base_a, price_a)
            self._buy_full(context, base_b, price_b)
        elif z < -Z_ENTRY and not has_a:
            self._close_if_held(context, base_b, price_b)
            self._buy_full(context, base_a, price_a)
        # EXIT: spread mean-reverted.
        elif abs(z) < Z_EXIT:
            self._close_if_held(context, base_a, price_a)
            self._close_if_held(context, base_b, price_b)

    def _close_if_held(self, context: Context, sym: str, price: float) -> None:
        if not context.has_position(sym, market=self.market):
            return
        pos = context.get_position(sym, market=self.market)
        context.create_order(
            target_symbol=sym, order_side=OrderSide.SELL,
            order_type=OrderType.LIMIT, price=price,
            amount=pos.get_amount(),
        )

    def _buy_full(self, context: Context, sym: str, price: float) -> None:
        cash = context.get_unallocated()
        if cash <= 0 or price <= 0:
            return
        amount = (cash * 0.995) / price
        context.create_order(
            target_symbol=sym, order_side=OrderSide.BUY,
            order_type=OrderType.LIMIT, price=price, amount=amount,
        )
