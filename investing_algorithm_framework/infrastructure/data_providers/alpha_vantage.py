import logging
import os.path
from datetime import datetime, timedelta, timezone
from typing import Union

import polars as pl
import pandas as pd

from investing_algorithm_framework.domain import (
    OperationalException,
    DataProvider,
    convert_polars_to_pandas,
    TimeFrame,
    DataType,
    DataSource,
    RESOURCE_DIRECTORY,
    DATA_DIRECTORY,
)

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


class AlphaVantageOHLCVDataProvider(DataProvider):
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
    data_type = DataType.OHLCV
    data_provider_identifier = "alpha_vantage_ohlcv_data_provider"
    storage_directory = None

    def __init__(
        self,
        symbol: str = None,
        time_frame: str = None,
        market: str = None,
        window_size=None,
        warmup_window=None,
        data_provider_identifier: str = None,
        storage_directory=None,
        pandas: bool = False,
        config=None
    ):
        if warmup_window is not None and window_size is None:
            window_size = warmup_window

        if data_provider_identifier is None:
            data_provider_identifier = self.data_provider_identifier

        super().__init__(
            symbol=symbol,
            market=market,
            time_frame=time_frame,
            window_size=window_size,
            data_provider_identifier=data_provider_identifier,
            storage_directory=storage_directory,
            config=config,
        )
        self.pandas = pandas
        self.data = None
        self._start_date_data_source = None
        self._end_date_data_source = None
        self.missing_data_point_dates = []
        self.total_number_of_data_points = 0
        self.data_file_path = None

        if storage_directory is not None:
            self.storage_directory = storage_directory

    def has_data(
        self,
        data_source: DataSource,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> bool:
        market = data_source.market
        data_type = data_source.data_type

        if not DataType.OHLCV.equals(data_type):
            return False

        if market is None:
            return False

        if market.upper() != "ALPHA_VANTAGE":
            return False

        start_date = start_date or data_source.start_date
        end_date = end_date or data_source.end_date

        # If date range specified, check storage first
        if start_date is not None and end_date is not None:
            data = self._get_data_from_storage(
                symbol=data_source.symbol,
                time_frame=data_source.time_frame,
                storage_path=data_source.storage_path,
                start_date=start_date,
                end_date=end_date,
            )

            if data is not None:
                return True

        # Validate time frame is supported
        tf = data_source.time_frame

        if hasattr(tf, "value"):
            tf = tf.value

        if tf not in TIMEFRAME_TO_AV:
            return False

        return True

    def prepare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date,
        fill_missing_data: bool = False,
        show_progress: bool = False,
    ) -> None:
        # Calculate required start date based on warmup window
        required_start_date = backtest_start_date

        if self.window_size is not None:
            n_minutes = TimeFrame.from_value(
                self.time_frame
            ).amount_of_minutes
            required_start_date = backtest_start_date - timedelta(
                minutes=n_minutes * self.window_size
            )

        # Check storage first
        data = self._get_data_from_storage(
            symbol=self.symbol,
            time_frame=self.time_frame,
            storage_path=self.get_storage_directory(),
            start_date=required_start_date,
            end_date=backtest_end_date,
        )

        if data is None:
            if show_progress:
                logger.info(
                    f"Downloading Alpha Vantage data for {self.symbol} "
                    f"from {required_start_date} to {backtest_end_date}"
                )

            data = self._download_ohlcv(
                symbol=self.symbol,
                time_frame=self.time_frame,
                start_date=required_start_date,
                end_date=backtest_end_date,
                api_key=self._get_api_key(),
            )

            # Save to storage
            storage_dir = self.get_storage_directory()

            if storage_dir is not None:
                self._save_data_to_storage(
                    symbol=self.symbol,
                    time_frame=self.time_frame,
                    start_date=required_start_date,
                    end_date=backtest_end_date,
                    data=data,
                    storage_directory_path=storage_dir,
                )

        self.data = data

        if self.data is None or len(self.data) == 0:
            raise OperationalException(
                f"No data available for {self.symbol} in the date range "
                f"{required_start_date} - {backtest_end_date}. "
                f"Please ensure the symbol is valid on Alpha Vantage."
            )

        self._start_date_data_source = self.data["Datetime"].min()
        self._end_date_data_source = self.data["Datetime"].max()
        self.total_number_of_data_points = len(self.data)

    def get_backtest_data(
        self,
        backtest_index_date: datetime,
        backtest_start_date: datetime = None,
        backtest_end_date: datetime = None,
        data_source: DataSource = None,
    ):
        if self.data is None:
            return None

        if self.window_size is not None:
            n_minutes = TimeFrame.from_value(
                self.time_frame
            ).amount_of_minutes
            start = backtest_index_date - timedelta(
                minutes=n_minutes * self.window_size
            )
        else:
            start = backtest_start_date

        filtered = self.data.filter(
            (pl.col("Datetime") >= start)
            & (pl.col("Datetime") <= backtest_index_date)
        )

        if self.pandas:
            return convert_polars_to_pandas(filtered)

        return filtered

    def get_data(
        self,
        date: datetime = None,
        start_date: datetime = None,
        end_date: datetime = None,
        save: bool = False,
    ) -> Union[pl.DataFrame, pd.DataFrame]:
        if self.symbol is None:
            raise OperationalException(
                "Symbol is not set. Please set the symbol "
                "before calling get_data."
            )

        if self.time_frame is None:
            raise OperationalException(
                "Time frame is not set. Please set the time frame "
                "before requesting ohlcv data."
            )

        # Handle date/window_size to derive start_date/end_date
        if date is not None and self.window_size is not None:
            start_date = self.create_start_date(
                end_date=date,
                time_frame=self.time_frame,
                window_size=self.window_size,
            )
            end_date = date
        else:
            if start_date is None and end_date is None \
                    and self.window_size is None:
                raise OperationalException(
                    "A start date or end date or window size is required "
                    "to retrieve ohlcv data."
                )

            if start_date is not None and end_date is None:
                end_date = datetime.now(tz=timezone.utc)

            if end_date is not None and start_date is None \
                    and self.window_size is not None:
                start_date = self.create_start_date(
                    end_date=end_date,
                    time_frame=self.time_frame,
                    window_size=self.window_size,
                )

        if start_date is None and end_date is None:
            end_date = datetime.now(tz=timezone.utc)
            start_date = self.create_start_date(
                end_date=end_date,
                time_frame=self.time_frame,
                window_size=self.window_size,
            )

        # Check storage first
        data = self._get_data_from_storage(
            symbol=self.symbol,
            time_frame=self.time_frame,
            storage_path=self.get_storage_directory(),
            start_date=start_date,
            end_date=end_date,
        )

        if data is None:
            data = self._download_ohlcv(
                symbol=self.symbol,
                time_frame=self.time_frame,
                start_date=start_date,
                end_date=end_date,
                api_key=self._get_api_key(),
            )

            if save:
                storage_dir = self.get_storage_directory()

                if storage_dir is None:
                    raise OperationalException(
                        "Storage directory is not set for "
                        "the AlphaVantageOHLCVDataProvider."
                    )

                self._save_data_to_storage(
                    symbol=self.symbol,
                    time_frame=self.time_frame,
                    start_date=start_date,
                    end_date=end_date,
                    data=data,
                    storage_directory_path=storage_dir,
                )

        if self.pandas:
            data = convert_polars_to_pandas(data)

        return data

    def copy(self, data_source) -> "AlphaVantageOHLCVDataProvider":
        if data_source.symbol is None or data_source.symbol == "":
            raise OperationalException(
                "DataSource has no `symbol` attribute specified, "
                "please specify the symbol attribute in the "
                "data source specification before using the "
                "Alpha Vantage OHLCV data provider"
            )

        if data_source.time_frame is None or data_source.time_frame == "":
            raise OperationalException(
                "DataSource has no `time_frame` attribute specified, "
                "please specify the time_frame attribute in the "
                "data source specification before using the "
                "Alpha Vantage OHLCV data provider"
            )

        storage_path = data_source.storage_path

        if storage_path is None:
            storage_path = self.get_storage_directory()

        provider = AlphaVantageOHLCVDataProvider(
            symbol=data_source.symbol,
            time_frame=data_source.time_frame,
            market=data_source.market,
            warmup_window=data_source.warmup_window,
            data_provider_identifier=data_source.data_provider_identifier,
            storage_directory=storage_path,
            config=self.config,
            pandas=data_source.pandas,
        )
        provider.data = self.data
        provider.missing_data_point_dates = self.missing_data_point_dates
        provider._start_date_data_source = self._start_date_data_source
        provider._end_date_data_source = self._end_date_data_source
        provider.data_file_path = self.data_file_path
        provider.market_credentials = self.market_credentials
        return provider

    def get_number_of_data_points(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> int:
        n_minutes = TimeFrame.from_value(
            self.time_frame
        ).amount_of_minutes
        delta = end_date - start_date
        return int(delta.total_seconds() / (n_minutes * 60))

    def get_missing_data_dates(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> list:
        missing_dates = [
            date for date in self.missing_data_point_dates
            if start_date <= date <= end_date
        ]
        return missing_dates

    def get_data_source_file_path(self) -> Union[str, None]:
        return self.data_file_path

    # ── Private helpers ─────────────────────────────────────────

    def _get_api_key(self) -> str:
        credential = self.get_credential("ALPHA_VANTAGE")

        if credential is not None:
            return credential.api_key

        raise OperationalException(
            "Alpha Vantage requires an API key. "
            "Configure it with: app.add_market_credential("
            "MarketCredential(market='ALPHA_VANTAGE', "
            "api_key='your_key'))"
        )

    def _get_av_config(self) -> tuple:
        tf = self.time_frame

        if hasattr(tf, "value"):
            tf = tf.value

        config = TIMEFRAME_TO_AV.get(tf)

        if config is None:
            raise OperationalException(
                f"Time frame '{tf}' is not supported by Alpha Vantage. "
                f"Supported time frames: "
                f"{list(TIMEFRAME_TO_AV.keys())}"
            )

        return config

    @staticmethod
    def _download_ohlcv(
        symbol: str,
        time_frame,
        start_date: datetime,
        end_date: datetime,
        api_key: str,
    ) -> pl.DataFrame:
        _ensure_alpha_vantage()
        from alpha_vantage.timeseries import TimeSeries

        tf = time_frame

        if hasattr(tf, "value"):
            tf = tf.value

        av_config = TIMEFRAME_TO_AV.get(tf)

        if av_config is None:
            raise OperationalException(
                f"Time frame '{tf}' is not supported by Alpha Vantage."
            )

        series_type, interval = av_config
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

    def _get_data_from_storage(
        self,
        symbol: str,
        time_frame,
        storage_path: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
    ):
        if storage_path is None:
            return None

        tf = time_frame
        if hasattr(tf, "value"):
            tf = tf.value

        safe_symbol = symbol.replace("/", "-")
        file_name = f"{safe_symbol}_{tf}_alpha_vantage.csv"
        file_path = os.path.join(storage_path, file_name)

        if not os.path.exists(file_path):
            return None

        try:
            data = pl.read_csv(file_path)

            if "Datetime" not in data.columns:
                return None

            data = data.with_columns(
                pl.col("Datetime").str.to_datetime().dt.replace_time_zone(
                    "UTC"
                )
            )

            if start_date is not None:
                data = data.filter(pl.col("Datetime") >= start_date)

            if end_date is not None:
                data = data.filter(pl.col("Datetime") <= end_date)

            if len(data) == 0:
                return None

            return data
        except Exception as e:
            logger.error(
                f"Error reading Alpha Vantage data from storage: {e}"
            )
            return None

    @staticmethod
    def _save_data_to_storage(
        symbol: str,
        time_frame,
        start_date: datetime,
        end_date: datetime,
        data: pl.DataFrame,
        storage_directory_path: str,
    ):
        if data is None or len(data) == 0:
            return

        tf = time_frame
        if hasattr(tf, "value"):
            tf = tf.value

        os.makedirs(storage_directory_path, exist_ok=True)
        safe_symbol = symbol.replace("/", "-")
        file_name = f"{safe_symbol}_{tf}_alpha_vantage.csv"
        file_path = os.path.join(storage_directory_path, file_name)

        write_data = data.with_columns(
            pl.col("Datetime").dt.strftime("%Y-%m-%d %H:%M:%S")
        )
        write_data.write_csv(file_path)

    def get_storage_directory(self):
        if self.storage_directory is not None:
            return self.storage_directory

        if self.config is not None \
                and RESOURCE_DIRECTORY in self.config:
            return os.path.join(
                self.config[RESOURCE_DIRECTORY], DATA_DIRECTORY
            )

        return None
