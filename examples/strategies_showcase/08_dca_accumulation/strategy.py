"""Dollar-cost averaging: weekly fixed-EUR buys, monthly recurring deposit.

Two pieces working together:

1. **Weekly buy** (`DCAStrategy.run_strategy`) — every 7 days, buy a
   fixed EUR amount of BTC.
2. **Monthly deposit** — declared on the market via
   ``app.add_market(deposit_schedule=[...], auto_sync=True)``. Both in
   live and backtest mode the framework's
   :meth:`Context.sync_portfolio` absorbs the new cash on each
   iteration. No bespoke task needed — see ``backtest.py``.
"""
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
MARKET = "BITVAVO"
DCA_AMOUNT_EUR = 25.0


class DCAStrategy(TradingStrategy):
    algorithm_id = "dca-weekly"
    time_unit = TimeUnit.DAY
    interval = 7
    market = MARKET
    trading_symbol = "EUR"
    symbols = [SYMBOL.split("/")[0]]

    data_sources = [
        DataSource(
            identifier=f"{SYMBOL}-ohlcv",
            data_type=DataType.OHLCV, market=market, symbol=SYMBOL,
            time_frame="1d", warmup_window=2, pandas=True,
        )
    ]

    def run_strategy(self, context: Context, data: Dict[str, Any]) -> None:
        df = data[f"{SYMBOL}-ohlcv"]
        if len(df) == 0:
            return
        price = float(df["Close"].iloc[-1])
        if price <= 0:
            return
        cash = context.get_unallocated()
        if cash < DCA_AMOUNT_EUR:
            return
        context.create_order(
            target_symbol=self.symbols[0],
            order_side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=price,
            amount=(DCA_AMOUNT_EUR * 0.995) / price,
        )
