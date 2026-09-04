"""Trend-following strategy: EMA(fast) crossing EMA(slow)."""
from __future__ import annotations

from typing import Any, Dict, Iterable

import pandas as pd
from pyindicators import crossover, crossunder, ema

from investing_algorithm_framework import (
    DataSource,
    DataType,
    Schedule,
    SignalSeries,
    SignalSide,
    TimeUnit,
    TradingStrategy,
    signal_series_from_column,
)


class TrendFollowingStrategy(TradingStrategy):
    algorithm_id = "trend-following-ema-crossover"
    schedule = Schedule.every(24, TimeUnit.HOUR)
    market = "BITVAVO"

    def __init__(
        self,
        symbol: str = "BTC/EUR",
        time_frame: str = "1d",
        fast_period: int = 20,
        slow_period: int = 50,
    ):
        self.symbol = symbol
        self.time_frame = time_frame
        self.fast_period = fast_period
        self.slow_period = slow_period

        symbols = [symbol.split("/")[0]]
        data_sources = [
            DataSource(
                identifier=f"{symbol}-ohlcv",
                data_type=DataType.OHLCV,
                market=self.market,
                symbol=symbol,
                time_frame=time_frame,
                warmup_window=slow_period + 10,
                pandas=True,
            )
        ]
        super().__init__(
            algorithm_id=self.algorithm_id,
            symbols=symbols,
            data_sources=data_sources,
        )
        self.set_parameters({
            "symbol": symbol,
            "time_frame": time_frame,
            "fast_period": fast_period,
            "slow_period": slow_period,
        })

    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = ema(df, period=self.fast_period,
                 source_column="Close", result_column="ema_fast")
        df = ema(df, period=self.slow_period,
                 source_column="Close", result_column="ema_slow")
        df = crossover(df, first_column="ema_fast",
                       second_column="ema_slow", result_column="x_up")
        df = crossunder(df, first_column="ema_fast",
                        second_column="ema_slow", result_column="x_dn")
        df["x_up"] = df["x_up"].fillna(False).astype(bool)
        df["x_dn"] = df["x_dn"].fillna(False).astype(bool)
        return df

    def generate_signal_series(
        self, data: Dict[str, Any]
    ) -> Iterable[SignalSeries]:
        df = self._prepare(data[f"{self.symbol}-ohlcv"])
        yield signal_series_from_column(
            df, "x_up",
            side=SignalSide.OPEN_LONG,
            symbol=self.symbols[0],
            source="ema_cross",
        )
        yield signal_series_from_column(
            df, "x_dn",
            side=SignalSide.CLOSE_LONG,
            symbol=self.symbols[0],
            source="ema_cross",
        )
