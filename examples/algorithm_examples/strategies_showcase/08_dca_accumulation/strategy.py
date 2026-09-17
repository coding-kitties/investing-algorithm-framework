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
MARKET = "BITVAVO"
DCA_AMOUNT_EUR = 25.0


class DCAStrategy(TradingStrategy):
    algorithm_id = "dca-weekly"
    schedule = Schedule.every(7, TimeUnit.DAY)
    market = MARKET
    symbols = [BASE]

    data_sources = [
        DataSource(
            identifier=f"{SYMBOL}-ohlcv",
            data_type=DataType.OHLCV, market=market, symbol=SYMBOL,
            time_frame="1d", warmup_window=2, pandas=True,
        )
    ]

    position_sizes = [
        PositionSize(symbol=BASE, fixed_amount=DCA_AMOUNT_EUR),
    ]

    def generate_signals(
        self, context: Context, data: Dict[str, Any]
    ) -> Iterable[Signal]:
        df = data[f"{SYMBOL}-ohlcv"]
        if len(df) == 0:
            return
        if float(df["Close"].iloc[-1]) <= 0:
            return
        if context.get_unallocated() < DCA_AMOUNT_EUR:
            return
        yield Signal(symbol=BASE, side=SignalSide.SCALE_IN, source="dca")
