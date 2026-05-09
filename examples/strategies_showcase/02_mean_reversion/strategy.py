"""Mean-reversion strategy: Bollinger + RSI."""
from __future__ import annotations

from typing import Any, Dict

import pandas as pd
from pyindicators import bollinger_bands, rsi

from investing_algorithm_framework import (
    DataSource,
    DataType,
    TimeUnit,
    TradingStrategy,
)


class MeanReversionStrategy(TradingStrategy):
    algorithm_id = "mean-reversion-bollinger-rsi"
    time_unit = TimeUnit.HOUR
    interval = 24
    market = "BITVAVO"
    trading_symbol = "EUR"

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
            trading_symbol=self.trading_symbol,
            data_sources=data_sources,
            time_unit=self.time_unit,
            interval=self.interval,
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
        return df

    def generate_buy_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        df = self._prepare(data[f"{self.symbol}-ohlcv"])
        sig = (df["Close"] < df["bb_lo"]) & (df["rsi"] < self.rsi_buy_below)
        return {self.symbols[0]: sig.fillna(False).astype(bool)}

    def generate_sell_signals(
        self, data: Dict[str, Any]
    ) -> Dict[str, pd.Series]:
        df = self._prepare(data[f"{self.symbol}-ohlcv"])
        sig = (df["Close"] > df["bb_mid"]) | (df["rsi"] > self.rsi_sell_above)
        return {self.symbols[0]: sig.fillna(False).astype(bool)}
