import logging
from datetime import datetime

import polars as pl
import pandas as pd

from investing_algorithm_framework.domain import (
    OperationalException,
)
from .ohlcv_base import OHLCVDataProviderBase

logger = logging.getLogger("investing_algorithm_framework")

# Mapping from framework TimeFrame values to Alpha Vantage function/interval
# Alpha Vantage uses different API functions for different granularities:
# - TIME_SERIES_INTRADAY for sub-daily (1min, 5min, 15min, 30min, 60min)
# - TIME_SERIES_DAILY for daily
# - TIME_SERIES_WEEKLY for weekly
# - TIME_SERIES_MONTHLY for monthly
TIMEFRAME_TO_AV = {
    "1m": ("INTRADAY", "1min"),
    "5m": ("INTRADAY", "5min"),
    "15m": ("INTRADAY", "15min"),
    "30m": ("INTRADAY", "30min"),
    "1h": ("INTRADAY", "60min"),
    "1d": ("DAILY", None),
    "1W": ("WEEKLY", None),
    "1M": ("MONTHLY", None),
}


def _ensure_alpha_vantage():
    """Lazily import alpha_vantage and raise a clear error if missing."""
    try:
        import alpha_vantage
        return alpha_vantage
    except ImportError:
        raise ImportError(
            "alpha_vantage is required for Alpha Vantage data providers. "
            "Install it with: pip install "
            "investing-algorithm-framework[alpha_vantage]"
        )


class AlphaVantageOHLCVDataProvider(OHLCVDataProviderBase):
    """
    Data provider for OHLCV data from Alpha Vantage via the
    alpha_vantage library. Supports stocks, forex, and crypto.

    Requires an API key configured via MarketCredential:

        app.add_market_credential(
            MarketCredential(
                market="ALPHA_VANTAGE",
                api_key="your_api_key",
            )
        )

    Usage:
        DataSource(
            identifier="aapl_ohlcv",
            market="ALPHA_VANTAGE",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
    """

    market_name = "ALPHA_VANTAGE"
    timeframe_map = TIMEFRAME_TO_AV
    data_provider_identifier = "alpha_vantage_ohlcv_data_provider"

    def _download_ohlcv(
        self,
        symbol: str,
        time_frame,
        start_date: datetime,
        end_date: datetime,
    ) -> pl.DataFrame:
        _ensure_alpha_vantage()
        from alpha_vantage.timeseries import TimeSeries

        av_config = self._get_provider_interval()
        series_type, interval = av_config
        api_key = self._get_api_key()
        ts = TimeSeries(key=api_key, output_format="pandas")

        try:
            if series_type == "INTRADAY":
                df, _ = ts.get_intraday(
                    symbol=symbol,
                    interval=interval,
                    outputsize="full",
                )
            elif series_type == "DAILY":
                df, _ = ts.get_daily(
                    symbol=symbol,
                    outputsize="full",
                )
            elif series_type == "WEEKLY":
                df, _ = ts.get_weekly(symbol=symbol)
            elif series_type == "MONTHLY":
                df, _ = ts.get_monthly(symbol=symbol)
            else:
                raise OperationalException(
                    f"Unknown Alpha Vantage series type: {series_type}"
                )
        except Exception as e:
            logger.error(f"Error downloading Alpha Vantage data: {e}")
            return pl.DataFrame(
                schema={
                    "Datetime": pl.Datetime("us", "UTC"),
                    "Open": pl.Float64,
                    "High": pl.Float64,
                    "Low": pl.Float64,
                    "Close": pl.Float64,
                    "Volume": pl.Float64,
                }
            )

        if df.empty:
            return pl.DataFrame(
                schema={
                    "Datetime": pl.Datetime("us", "UTC"),
                    "Open": pl.Float64,
                    "High": pl.Float64,
                    "Low": pl.Float64,
                    "Close": pl.Float64,
                    "Volume": pl.Float64,
                }
            )

        # Alpha Vantage column names: 1. open, 2. high, 3. low,
        # 4. close, 5. volume
        df = df.rename(columns={
            "1. open": "Open",
            "2. high": "High",
            "3. low": "Low",
            "4. close": "Close",
            "5. volume": "Volume",
        })
        df = df.reset_index()
        df = df.rename(columns={"date": "Datetime"})

        # Ensure timezone-aware UTC
        df["Datetime"] = pd.to_datetime(df["Datetime"])

        if df["Datetime"].dt.tz is None:
            df["Datetime"] = df["Datetime"].dt.tz_localize("UTC")
        else:
            df["Datetime"] = df["Datetime"].dt.tz_convert("UTC")

        # Filter to requested date range
        df = df[
            (df["Datetime"] >= start_date)
            & (df["Datetime"] <= end_date)
        ]

        # Sort chronologically
        df = df.sort_values("Datetime").reset_index(drop=True)

        # Convert to polars
        polars_df = pl.from_pandas(
            df[["Datetime", "Open", "High", "Low", "Close", "Volume"]]
        )

        return polars_df

    def _storage_file_suffix(self) -> str:
        return "alpha_vantage"
