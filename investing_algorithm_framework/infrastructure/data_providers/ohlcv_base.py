import logging
import os
from abc import abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Union, List, Dict

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


class OHLCVDataProviderBase(DataProvider):
    """
    Intermediate base class for all OHLCV data providers. Handles:

    - Constructor boilerplate (symbol, time_frame, market, storage, etc.)
    - `get_data()` — date/window logic, storage cache check, download
    - `prepare_backtest_data()` — download + cache for backtesting
    - `get_backtest_data()` — slice cached data by index date
    - `copy()` — clone instance for a specific DataSource
    - `get_number_of_data_points()` / `get_missing_data_dates()`
    - CSV-based storage helpers

    Subclasses only need to implement:

    - `market_name` (class attribute) — e.g. "YAHOO", "ALPHA_VANTAGE"
    - `timeframe_map` (class attribute) — maps framework TimeFrame
      strings to provider-specific values
    - `_download_ohlcv()` — the actual API call
    - `_validate_symbol()` (optional) — extra symbol validation
      in `has_data()`
    """

    data_type = DataType.OHLCV
    data_provider_identifier: str = None
    storage_directory = None

    # ── Subclass must define these ──────────────────────────────

    # The market string this provider handles, e.g. "YAHOO"
    market_name: str = None

    # Mapping from framework TimeFrame string → provider-specific value
    # e.g. {"1d": "1d", "1W": "1wk"} for Yahoo
    timeframe_map: Dict[str, object] = {}

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
        config=None,
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

    # ── Template methods (shared logic) ─────────────────────────

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

        if market.upper() != self.market_name:
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

        # Validate timeframe is supported
        tf = data_source.time_frame

        if hasattr(tf, "value"):
            tf = tf.value

        if tf not in self.timeframe_map:
            return False

        # Provider-specific symbol validation (optional override)
        return self._validate_symbol(data_source)

    def prepare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date,
        fill_missing_data: bool = False,
        show_progress: bool = False,
    ) -> None:
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
                    f"Downloading {self.market_name} data for {self.symbol} "
                    f"from {required_start_date} to {backtest_end_date}"
                )

            data = self._download_ohlcv(
                symbol=self.symbol,
                time_frame=self.time_frame,
                start_date=required_start_date,
                end_date=backtest_end_date,
            )

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
                f"Please ensure the symbol is valid on {self.market_name}."
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

        start_date, end_date = self._resolve_date_range(
            date=date,
            start_date=start_date,
            end_date=end_date,
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
            )

            if save:
                storage_dir = self.get_storage_directory()

                if storage_dir is None:
                    raise OperationalException(
                        "Storage directory is not set for "
                        f"the {self.__class__.__name__}."
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

    def copy(self, data_source) -> "OHLCVDataProviderBase":
        if data_source.symbol is None or data_source.symbol == "":
            raise OperationalException(
                "DataSource has no `symbol` attribute specified, "
                "please specify the symbol attribute in the "
                f"data source specification before using the "
                f"{self.market_name} OHLCV data provider"
            )

        if data_source.time_frame is None or data_source.time_frame == "":
            raise OperationalException(
                "DataSource has no `time_frame` attribute specified, "
                "please specify the time_frame attribute in the "
                f"data source specification before using the "
                f"{self.market_name} OHLCV data provider"
            )

        storage_path = data_source.storage_path

        if storage_path is None:
            storage_path = self.get_storage_directory()

        provider = self.__class__(
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
        return [
            date for date in self.missing_data_point_dates
            if start_date <= date <= end_date
        ]

    def get_data_source_file_path(self) -> Union[str, None]:
        return self.data_file_path

    # ── Subclass hooks ──────────────────────────────────────────

    @abstractmethod
    def _download_ohlcv(
        self,
        symbol: str,
        time_frame,
        start_date: datetime,
        end_date: datetime,
    ) -> pl.DataFrame:
        """
        Download OHLCV data from the external API.

        Must return a Polars DataFrame with columns:
        Datetime, Open, High, Low, Close, Volume

        Datetime must be timezone-aware UTC.
        """
        raise NotImplementedError

    def _validate_symbol(self, data_source: DataSource) -> bool:
        """
        Optional hook for subclasses to validate whether a symbol
        exists on the provider. Default returns True.
        """
        return True

    # ── Shared private helpers ──────────────────────────────────

    def _get_provider_interval(self) -> object:
        """Get the provider-specific interval for the current time frame."""
        tf = self.time_frame

        if hasattr(tf, "value"):
            tf = tf.value

        interval = self.timeframe_map.get(tf)

        if interval is None:
            raise OperationalException(
                f"Time frame '{tf}' is not supported by {self.market_name}. "
                f"Supported time frames: "
                f"{list(self.timeframe_map.keys())}"
            )

        return interval

    def _get_api_key(self, market_name: str = None) -> str:
        """
        Get API key from MarketCredential. Only call this from
        providers that require authentication.
        """
        name = market_name or self.market_name
        credential = self.get_credential(name)

        if credential is not None:
            return credential.api_key

        raise OperationalException(
            f"{name} requires an API key. "
            f"Configure it with: app.add_market_credential("
            f"MarketCredential(market='{name}', "
            f"api_key='your_key'))"
        )

    def _resolve_date_range(
        self,
        date: datetime = None,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> tuple:
        """
        Resolve start_date and end_date from the various input
        combinations (date, start_date, end_date, window_size).
        """
        if date is not None and self.window_size is not None:
            start_date = self._create_start_date(
                end_date=date,
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
                start_date = self._create_start_date(
                    end_date=end_date,
                )

        if start_date is None and end_date is None:
            end_date = datetime.now(tz=timezone.utc)
            start_date = self._create_start_date(
                end_date=end_date,
            )

        return start_date, end_date

    def _create_start_date(self, end_date: datetime) -> datetime:
        """Calculate start date from end_date and window_size."""
        n_minutes = TimeFrame.from_value(
            self.time_frame
        ).amount_of_minutes
        return end_date - timedelta(
            minutes=self.window_size * n_minutes
        )

    def _storage_file_suffix(self) -> str:
        """
        Returns a suffix for storage file names.
        Override if needed, default uses market_name lower-cased.
        """
        return self.market_name.lower()

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
        file_name = f"{safe_symbol}_{tf}_{self._storage_file_suffix()}.csv"
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
                f"Error reading {self.market_name} data from storage: {e}"
            )
            return None

    @staticmethod
    def _save_data_to_storage_impl(
        data: pl.DataFrame,
        file_path: str,
    ):
        """Write a Polars DataFrame to CSV with stringified Datetime."""
        if data is None or len(data) == 0:
            return

        write_data = data.with_columns(
            pl.col("Datetime").dt.strftime("%Y-%m-%d %H:%M:%S")
        )
        write_data.write_csv(file_path)

    def _save_data_to_storage(
        self,
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
        file_name = f"{safe_symbol}_{tf}_{self._storage_file_suffix()}.csv"
        file_path = os.path.join(storage_directory_path, file_name)

        self._save_data_to_storage_impl(data, file_path)

    def get_storage_directory(self):
        if self.storage_directory is not None:
            return self.storage_directory

        if self.config is not None \
                and RESOURCE_DIRECTORY in self.config:
            return os.path.join(
                self.config[RESOURCE_DIRECTORY], DATA_DIRECTORY
            )

        return None
