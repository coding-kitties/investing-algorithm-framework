"""Mean-reversion strategy: Bollinger + RSI."""
from __future__ import annotations

from typing import Any, Dict, Iterable

import pandas as pd
from pyindicators import bollinger_bands, rsi

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


class MeanReversionStrategy(TradingStrategy):
    algorithm_id = "mean-reversion-bollinger-rsi"
    schedule = Schedule.every(24, TimeUnit.HOUR)
    market = "BITVAVO"

    def __init__(
        self,
        symbol: str = "BTC/EUR",
        time_frame: str = "1d",
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_period: int = 14,
        rsi_buy_below: float = 30.0,
        rsi_sell_above: float = 70.0,
    ):
        self.symbol = symbol
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_period = rsi_period
        self.rsi_buy_below = rsi_buy_below
        self.rsi_sell_above = rsi_sell_above

        symbols = [symbol.split("/")[0]]
        data_sources = [
            DataSource(
                identifier=f"{symbol}-ohlcv",
                data_type=DataType.OHLCV,
                market=self.market,
                symbol=symbol,
                time_frame=time_frame,
                warmup_window=max(bb_period, rsi_period) + 20,
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
            "bb_period": bb_period,
            "bb_std": bb_std,
            "rsi_period": rsi_period,
            "rsi_buy_below": rsi_buy_below,
            "rsi_sell_above": rsi_sell_above,
        })

    def _prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        df = bollinger_bands(
            df,
            source_column="Close",
            period=self.bb_period,
            std_dev=self.bb_std,
            upper_band_column_result_column="bb_up",
            middle_band_column_result_column="bb_mid",
            lower_band_column_result_column="bb_lo",
        )
        df = rsi(df, period=self.rsi_period,
                 source_column="Close", result_column="rsi")
        df["entry"] = (
            (df["Close"] < df["bb_lo"])
            & (df["rsi"] < self.rsi_buy_below)
        ).fillna(False).astype(bool)
        df["exit"] = (
            (df["Close"] > df["bb_mid"])
            | (df["rsi"] > self.rsi_sell_above)
        ).fillna(False).astype(bool)
        return df

    def generate_signal_series(
        self, data: Dict[str, Any]
    ) -> Iterable[SignalSeries]:
        df = self._prepare(data[f"{self.symbol}-ohlcv"])
        yield signal_series_from_column(
            df, "entry",
            side=SignalSide.OPEN_LONG,
            symbol=self.symbols[0],
            source="bollinger_rsi",
        )
        yield signal_series_from_column(
            df, "exit",
            side=SignalSide.CLOSE_LONG,
            symbol=self.symbols[0],
            source="bollinger_rsi",
        )
