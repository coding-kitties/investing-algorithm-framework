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
    DATETIME_FORMAT_FILE_NAME,
)

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


class YahooOHLCVDataProvider(DataProvider):
    """
    Data provider for OHLCV data from Yahoo Finance via the yfinance
    library. Supports stocks, ETFs, indices, forex, and crypto.

    Uses the same pattern as CCXTOHLCVDataProvider:
    - `has_data()` checks if the market is "YAHOO" and validates the symbol
    - `get_data()` fetches live OHLCV data via yfinance
    - `prepare_backtest_data()` downloads and caches historical data
    - `get_backtest_data()` returns sliced data for backtesting
    - `copy()` creates a new instance for a specific data source

    Usage:
        DataSource(
            identifier="aapl_ohlcv",
            market="YAHOO",
            symbol="AAPL",
            data_type="OHLCV",
            time_frame="1d",
        )
    """
    data_type = DataType.OHLCV
    data_provider_identifier = "yahoo_ohlcv_data_provider"
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

        # Only handle YAHOO market
        if market.upper() != "YAHOO":
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

        # Validate the symbol exists on Yahoo Finance
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

    def prepare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date,
        fill_missing_data: bool = False,
        show_progress: bool = False,
    ) -> None:
        yf = _ensure_yfinance()
        interval = self._get_yfinance_interval()

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
                    f"Downloading Yahoo Finance data for {self.symbol} "
                    f"from {required_start_date} to {backtest_end_date}"
                )

            data = self._download_ohlcv(
                symbol=self.symbol,
                interval=interval,
                start_date=required_start_date,
                end_date=backtest_end_date,
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
                f"Please ensure the symbol is valid on Yahoo Finance."
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
            interval = self._get_yfinance_interval()
            data = self._download_ohlcv(
                symbol=self.symbol,
                interval=interval,
                start_date=start_date,
                end_date=end_date,
            )

            if save:
                storage_dir = self.get_storage_directory()

                if storage_dir is None:
                    raise OperationalException(
                        "Storage directory is not set for "
                        "the YahooOHLCVDataProvider."
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

    def copy(self, data_source) -> "YahooOHLCVDataProvider":
        if data_source.symbol is None or data_source.symbol == "":
            raise OperationalException(
                "DataSource has no `symbol` attribute specified, "
                "please specify the symbol attribute in the "
                "data source specification before using the "
                "Yahoo OHLCV data provider"
            )

        if data_source.time_frame is None or data_source.time_frame == "":
            raise OperationalException(
                "DataSource has no `time_frame` attribute specified, "
                "please specify the time_frame attribute in the "
                "data source specification before using the "
                "Yahoo OHLCV data provider"
            )

        storage_path = data_source.storage_path

        if storage_path is None:
            storage_path = self.get_storage_directory()

        provider = YahooOHLCVDataProvider(
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

    def _get_yfinance_interval(self) -> str:
        tf = self.time_frame

        if hasattr(tf, "value"):
            tf = tf.value

        interval = TIMEFRAME_TO_YFINANCE_INTERVAL.get(tf)

        if interval is None:
            raise OperationalException(
                f"Time frame '{tf}' is not supported by Yahoo Finance. "
                f"Supported time frames: "
                f"{list(TIMEFRAME_TO_YFINANCE_INTERVAL.keys())}"
            )

        return interval

    @staticmethod
    def _download_ohlcv(
        symbol: str,
        interval: str,
        start_date: datetime,
        end_date: datetime,
    ) -> pl.DataFrame:
        yf = _ensure_yfinance()

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
        file_name = f"{safe_symbol}_{tf}_yahoo.csv"
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
            logger.error(f"Error reading Yahoo data from storage: {e}")
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
        file_name = f"{safe_symbol}_{tf}_yahoo.csv"
        file_path = os.path.join(storage_directory_path, file_name)

        # Cast Datetime to string for CSV storage
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
