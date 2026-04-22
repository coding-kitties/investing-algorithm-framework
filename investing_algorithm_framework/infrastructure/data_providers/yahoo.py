import logging
from datetime import datetime, timedelta

import polars as pl
import pandas as pd

from investing_algorithm_framework.domain import (
    DataSource,
)
from .ohlcv_base import OHLCVDataProviderBase

logger = logging.getLogger("investing_algorithm_framework")

# Mapping from framework TimeFrame values to yfinance interval strings
TIMEFRAME_TO_YFINANCE_INTERVAL = {
    "1m": "1m",
    "2m": "2m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "1d": "1d",
    "1W": "1wk",
    "1M": "1mo",
}


def _ensure_yfinance():
    """Lazily import yfinance and raise a clear error if not installed."""
    try:
        import yfinance as yf
        return yf
    except ImportError:
        raise ImportError(
            "yfinance is required for Yahoo Finance data providers. "
            "Install it with: pip install "
            "investing-algorithm-framework[yahoo]"
        )


class YahooOHLCVDataProvider(OHLCVDataProviderBase):
    """
    Data provider for OHLCV data from Yahoo Finance via the yfinance
    library. Supports stocks, ETFs, indices, forex, and crypto.

    Usage:
        DataSource(
            identifier="aapl_ohlcv",
            market="YAHOO",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
    """

    market_name = "YAHOO"
    timeframe_map = TIMEFRAME_TO_YFINANCE_INTERVAL
    data_provider_identifier = "yahoo_ohlcv_data_provider"

    def _validate_symbol(self, data_source: DataSource) -> bool:
        """Validate the symbol exists on Yahoo Finance."""
        yf = _ensure_yfinance()

        try:
            ticker = yf.Ticker(data_source.symbol)
            info = ticker.info
            return info is not None and "symbol" in info
        except Exception as e:
            logger.error(
                f"Error checking Yahoo Finance symbol "
                f"{data_source.symbol}: {e}"
            )
            return False

    def _download_ohlcv(
        self,
        symbol: str,
        time_frame,
        start_date: datetime,
        end_date: datetime,
    ) -> pl.DataFrame:
        yf = _ensure_yfinance()
        interval = self._get_provider_interval()

        # yfinance expects string dates or datetime objects
        # Add 1 day to end_date because yfinance end is exclusive
        end_plus = end_date + timedelta(days=1)

        df = yf.download(
            tickers=symbol,
            start=start_date,
            end=end_plus,
            interval=interval,
            auto_adjust=True,
            progress=False,
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

        # Flatten MultiIndex columns if present (yfinance >= 0.2.31)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # Convert pandas DataFrame to polars
        df = df.reset_index()

        # Normalize the datetime column name
        datetime_col = "Date" if "Date" in df.columns else "Datetime"

        if datetime_col == "Date":
            df = df.rename(columns={"Date": "Datetime"})

        # Ensure timezone-aware UTC
        if df["Datetime"].dt.tz is None:
            df["Datetime"] = df["Datetime"].dt.tz_localize("UTC")
        else:
            df["Datetime"] = df["Datetime"].dt.tz_convert("UTC")

        # Select and order columns
        polars_df = pl.from_pandas(
            df[["Datetime", "Open", "High", "Low", "Close", "Volume"]]
        )

        return polars_df
