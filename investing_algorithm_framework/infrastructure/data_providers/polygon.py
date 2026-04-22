import logging
from datetime import datetime, timezone

import polars as pl
import pandas as pd

from investing_algorithm_framework.domain import (
    OperationalException,
)
from .ohlcv_base import OHLCVDataProviderBase

logger = logging.getLogger("investing_algorithm_framework")

# Mapping from framework TimeFrame values to Polygon.io timespan/multiplier
TIMEFRAME_TO_POLYGON = {
    "1m": ("minute", 1),
    "5m": ("minute", 5),
    "15m": ("minute", 15),
    "30m": ("minute", 30),
    "1h": ("hour", 1),
    "1d": ("day", 1),
    "1W": ("week", 1),
    "1M": ("month", 1),
}


def _ensure_polygon():
    """Lazily import polygon and raise a clear error if not installed."""
    try:
        import polygon
        return polygon
    except ImportError:
        raise ImportError(
            "polygon-api-client is required for Polygon.io data providers. "
            "Install it with: pip install "
            "investing-algorithm-framework[polygon]"
        )


class PolygonOHLCVDataProvider(OHLCVDataProviderBase):
    """
    Data provider for OHLCV data from Polygon.io via the
    polygon-api-client library. Supports US stocks, options,
    forex, and crypto.

    Requires an API key configured via MarketCredential:

        app.add_market_credential(
            MarketCredential(
                market="POLYGON",
                api_key="your_api_key",
            )
        )

    Usage:
        DataSource(
            identifier="aapl_ohlcv",
            market="POLYGON",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
    """

    market_name = "POLYGON"
    timeframe_map = TIMEFRAME_TO_POLYGON
    data_provider_identifier = "polygon_ohlcv_data_provider"

    def _download_ohlcv(
        self,
        symbol: str,
        time_frame,
        start_date: datetime,
        end_date: datetime,
    ) -> pl.DataFrame:
        _ensure_polygon()
        from polygon import RESTClient

        timespan, multiplier = self._get_provider_interval()
        api_key = self._get_api_key()
        client = RESTClient(api_key=api_key)

        try:
            aggs = client.get_aggs(
                ticker=symbol,
                multiplier=multiplier,
                timespan=timespan,
                from_=start_date.strftime("%Y-%m-%d"),
                to=end_date.strftime("%Y-%m-%d"),
                limit=50000,
            )
        except Exception as e:
            logger.error(f"Error downloading Polygon.io data: {e}")
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

        if not aggs:
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

        # Convert Polygon aggs to DataFrame
        records = []

        for agg in aggs:
            dt = datetime.fromtimestamp(
                agg.timestamp / 1000, tz=timezone.utc
            )
            records.append({
                "Datetime": dt,
                "Open": float(agg.open),
                "High": float(agg.high),
                "Low": float(agg.low),
                "Close": float(agg.close),
                "Volume": float(agg.volume),
            })

        df = pd.DataFrame(records)
        df = df.sort_values("Datetime").reset_index(drop=True)

        polars_df = pl.from_pandas(
            df[["Datetime", "Open", "High", "Low", "Close", "Volume"]]
        )

        return polars_df
