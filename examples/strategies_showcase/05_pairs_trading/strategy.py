"""Pairs trading (long-only, spot-friendly variant)."""
from __future__ import annotations

import math
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

SYMBOL_A = "BTC/EUR"
SYMBOL_B = "ETH/EUR"
BASE_A = SYMBOL_A.split("/")[0]
BASE_B = SYMBOL_B.split("/")[0]
WINDOW = 60
Z_ENTRY = 1.5
Z_EXIT = 0.3


class PairsTradingStrategy(TradingStrategy):
    algorithm_id = "pairs-trading-zscore"
    schedule = Schedule.every(1, TimeUnit.DAY)
    market = "BITVAVO"
    symbols = [BASE_A, BASE_B]

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

    position_sizes = [
        PositionSize(symbol=BASE_A, percentage_of_portfolio=99.0),
        PositionSize(symbol=BASE_B, percentage_of_portfolio=99.0),
    ]

    def generate_signals(
        self, context: Context, data: Dict[str, Any]
    ) -> Iterable[Signal]:
        df_a = data[f"{SYMBOL_A}-ohlcv"]
        df_b = data[f"{SYMBOL_B}-ohlcv"]
        if len(df_a) < WINDOW + 1 or len(df_b) < WINDOW + 1:
            return

        spread = (df_a["Close"].apply(math.log)
                  - df_b["Close"].apply(math.log)).tail(WINDOW + 1)
        mu = spread.iloc[:-1].mean()
        sd = spread.iloc[:-1].std()
        if sd == 0 or math.isnan(sd):
            return
        z = (spread.iloc[-1] - mu) / sd

        has_a = context.has_position(BASE_A, market=self.market)
        has_b = context.has_position(BASE_B, market=self.market)

        if z > Z_ENTRY and not has_b:
            if has_a:
                yield Signal(
                    symbol=BASE_A, side=SignalSide.CLOSE_LONG,
                    source="pairs",
                )
            yield Signal(
                symbol=BASE_B, side=SignalSide.OPEN_LONG, source="pairs",
            )
        elif z < -Z_ENTRY and not has_a:
            if has_b:
                yield Signal(
                    symbol=BASE_B, side=SignalSide.CLOSE_LONG,
                    source="pairs",
                )
            yield Signal(
                symbol=BASE_A, side=SignalSide.OPEN_LONG, source="pairs",
            )
        elif abs(z) < Z_EXIT:
            if has_a:
                yield Signal(
                    symbol=BASE_A, side=SignalSide.CLOSE_LONG,
                    source="pairs",
                )
            if has_b:
                yield Signal(
                    symbol=BASE_B, side=SignalSide.CLOSE_LONG,
                    source="pairs",
                )
