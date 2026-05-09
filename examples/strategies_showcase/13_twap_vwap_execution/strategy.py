"""Bar-level TWAP execution: parent order sliced into N child orders."""
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
PARENT_NOTIONAL_EUR = 500.0
SLICES = 10
START_AFTER_BARS = 5  # let warmup pass first


class TWAPExecutionStrategy(TradingStrategy):
    algorithm_id = "twap-bar-level"
    time_unit = TimeUnit.DAY
    interval = 1
    market = "BITVAVO"
    trading_symbol = "EUR"
    symbols = [SYMBOL.split("/")[0]]

    data_sources = [
        DataSource(
            identifier=f"{SYMBOL}-ohlcv",
            data_type=DataType.OHLCV, market=market, symbol=SYMBOL,
            time_frame="1d", warmup_window=10, pandas=True,
        )
    ]

    def __init__(self):
        super().__init__()
        self._bar_count = 0
        self._slices_done = 0
        self._slice_notional = PARENT_NOTIONAL_EUR / SLICES

    def run_strategy(self, context: Context, data: Dict[str, Any]) -> None:
        self._bar_count += 1
        if self._bar_count <= START_AFTER_BARS:
            return
        if self._slices_done >= SLICES:
            return

        df = data[f"{SYMBOL}-ohlcv"]
        if len(df) == 0:
            return
        price = float(df["Close"].iloc[-1])
        if price <= 0:
            return
        if context.get_unallocated() < self._slice_notional:
            return
        amount = (self._slice_notional * 0.995) / price
        context.create_order(
            target_symbol=self.symbols[0], order_side=OrderSide.BUY,
            order_type=OrderType.LIMIT, price=price, amount=amount,
        )
        self._slices_done += 1
