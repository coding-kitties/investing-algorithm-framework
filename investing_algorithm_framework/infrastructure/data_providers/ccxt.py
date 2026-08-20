import logging
import os.path
from datetime import datetime, timedelta, timezone
from time import sleep
from typing import Union, List

import ccxt
import pandas as pd
import polars as pl
from dateutil import parser

from investing_algorithm_framework.domain import OperationalException, \
    DATETIME_FORMAT, DataProvider, convert_polars_to_pandas, \
    NetworkError, TimeFrame, MarketCredential, DataType, DataSource, \
    RESOURCE_DIRECTORY, CCXT_DATETIME_FORMAT, DATA_DIRECTORY

logger = logging.getLogger("investing_algorithm_framework")


class CCXTOHLCVDataProvider(DataProvider):
    """
    Implementation of Data Provider for OHLCV data. OHLCV data
    will be downloaded with the CCXT library.

    If in backtest mode, and the data is already
    available in the storage path, it will be loaded from there. If the
    data is not available in the storage path, it will be fetched from the
    CCXT library and saved to the storage path in csv format.

    If the get_data method is called with a start and end date, the
    data provider will look if the data is already available in the
    storage directory. If this is the case, it will read the data
    from the csv file and return it.

    The CSV file should contain the following
    columns: Datetime, Open, High, Low, Close, Volume.
    The Datetime column should be in UTC timezone and in milliseconds.
    The data will be loaded into a Polars DataFrame and will be kept in memory.

    Attributes:
        data_type (DataType): The type of data provided by this provider,
            which is OHLCV.
        data_provider_identifier (str): Identifier for the CSV OHLCV data
            provider.
        _start_date_data_source (datetime): The start date of the data
            source, determined from the first row of the data.
        _end_date_data_source (datetime): The end date of the data
            source, determined from the last row of the data.
        data (polars.DataFrame): The OHLCV data loaded from the CSV file when
            in backtest mode.
    """
    data_type = DataType.OHLCV
    data_provider_identifier = "ccxt_ohlcv_data_provider"
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
        """
        Initialize the CCXT OHLCV Data Provider.

        Args:
            symbol (str): The symbol for which the data is provided.
            time_frame (str): The time frame for the data.
            market (str, optional): The market for the data. Defaults to None.
            window_size (int, optional): The window size for the data.
                Defaults to None.
            data_provider_identifier (str, optional): The identifier for the
                data provider.
            pandas (bool, optional): If True, the data will be returned
                as a pandas DataFrame instead of a Polars DataFrame.
            storage_directory: (str, optional): the storage directory where
                the OHLCV data need to be stored.
        """
        if warmup_window is not None and window_size is None:
            window_size = warmup_window

        if data_provider_identifier is None:
            data_provider_identifier = self.data_provider_identifier

        super().__init__(
            symbol=symbol,
            market=market,
            time_frame=time_frame,
            window_size=window_size,
            storage_directory=storage_directory,
            data_provider_identifier=data_provider_identifier,
            config=config
        )
        self._start_date_data_source = None
        self._end_date_data_source = None
        self._columns = ["Datetime", "Open", "High", "Low", "Close", "Volume"]
        self.pandas = pandas
        self.window_cache = {}
        self.data = None
        self.total_number_of_data_points = 0
        self.missing_data_point_dates = []
        self.data_file_path = None

    def has_data(
        self,
        data_source: DataSource,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> bool:
        """
        Implementation of the has_data method to check if
        the data provider has data for the given data source.

        If start_date and/or end_date are provided, first the
        storage_directory_will be checked for existence of the data.

        If nothing is found or start_date and/or end_date are not provided
        the ccxt library will be directly queried.

        Args:
            data_source (DataSource): The data source to check.
            start_date (datetime, optional): The start date for the data.
                Defaults to None.
            end_date (datetime, optional): The end date for the data.
                Defaults to None.

        Returns:
            bool: True if the data provider has data for the given data source,
                False otherwise.
        """
        market = data_source.market
        symbol = data_source.symbol
        data_type = data_source.data_type
        start_date = start_date or data_source.start_date
        end_date = end_date or data_source.end_date

        if not DataType.OHLCV.equals(data_type):
            return False

        if start_date is not None and end_date is not None:
            # Check if the data is available in the storage path
            data = self._get_data_from_storage(
                symbol=symbol,
                market=market,
                time_frame=data_source.time_frame,
                storage_path=(
                    data_source.storage_path or self.get_storage_directory()
                ),
                start_date=start_date,
                end_date=end_date
            )

            if data is not None:
                return True

        if market is None:
            market = "binance"

        # Check if ccxt has an exchange for the given market
        try:
            market = market.lower()
            exchange_class = getattr(ccxt, market)
            exchange = exchange_class()
            symbols = exchange.load_markets()
            symbols = list(symbols.keys())
            return symbol in symbols

        except ccxt.NetworkError:
            pass

        except Exception as e:
            logger.error(e)
            return False

    def prepare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date,
        fill_missing_data: bool = False,
        show_progress: bool = False,
    ) -> None:
        """
        Prepares backtest data for a given symbol and date range.

        Args:
            backtest_start_date (datetime): The start date for the
                backtest data.
            backtest_end_date (datetime): The end date for the
                backtest data.
            fill_missing_data (bool): If True, missing time series data
                entries will be filled automatically before creating
                the window cache.
            show_progress (bool): If True, print progress messages when
                filling missing data.

        Raises:
            OperationalException: If the backtest start date is before the
                start date of the data source or if the backtest end date is
                after the end date of the data source.

        Returns:
            None
        """
        # There must be at least backtest_start_date - window_size * time_frame
        # data available to create a sliding window.

        if self.window_size is not None:
            required_start_date = backtest_start_date - \
                timedelta(
                    minutes=TimeFrame.from_value(
                        self.time_frame
                    ).amount_of_minutes * self.window_size
                )
        else:
            required_start_date = backtest_start_date

        storage_directory_path = self.get_storage_directory()

        # Canonical merge-and-slice cache: reuses whatever is already on
        # disk for this (symbol, market, time_frame) and only downloads
        # the sub-range(s) not yet cached, instead of re-downloading the
        # full window on every backtest run that touches this symbol.
        if storage_directory_path is not None:
            data = self._get_or_fetch_data(
                symbol=self.symbol,
                market=self.market,
                time_frame=self.time_frame,
                storage_path=storage_directory_path,
                start_date=required_start_date,
                end_date=backtest_end_date,
                persist=True,
            )
        else:
            data = self.get_ohlcv(
                symbol=self.symbol,
                time_frame=self.time_frame,
                from_timestamp=required_start_date,
                market=self.market,
                to_timestamp=backtest_end_date,
            )

        self.data = data

        # Check if data is empty before attempting to fill missing data
        # fill_missing_timeseries_data cannot fill data if there's no
        # existing data to copy from
        if self.data is None or len(self.data) == 0:
            raise OperationalException(
                f"No data available for {self.symbol} in the date range "
                f"{required_start_date} - {backtest_end_date}. "
                f"Please ensure the data source file exists and contains "
                f"data for this date range. Storage directory: "
                f"{storage_directory_path}"
            )

        # Fill missing data if requested
        if fill_missing_data:
            from investing_algorithm_framework.services.data_providers.data \
                import fill_missing_timeseries_data, \
                get_missing_timeseries_data_entries

            # Get the frequency string based on time_frame
            time_frame_obj = TimeFrame.from_value(self.time_frame)
            freq_minutes = time_frame_obj.amount_of_minutes
            freq = f"{freq_minutes}min" if freq_minutes < 60 else \
                f"{freq_minutes // 60}h" if freq_minutes < 1440 else "D"

            # Check for missing dates
            missing_dates = get_missing_timeseries_data_entries(
                self.data,
                start=required_start_date,
                end=backtest_end_date,
                freq=freq
            )

            if len(missing_dates) > 0:
                if show_progress:
                    print(
                        f"[DEBUG] Filling {len(missing_dates)} missing "
                        f"dates for {self.symbol} {self.time_frame}"
                    )
                logger.info(
                    f"Filling {len(missing_dates)} missing dates for "
                    f"{self.symbol} {self.time_frame}"
                )

                # Fill the missing data (never write back to the
                # source file during backtest preparation)
                filled_data = fill_missing_timeseries_data(
                    self.data,
                    missing_dates=missing_dates,
                    save_to_file=False,
                )

                if filled_data is not None:
                    self.data = filled_data
                    data = filled_data

        # Check if data is empty before accessing min/max
        if self.data is None or len(self.data) == 0:
            raise OperationalException(
                f"No data available for {self.symbol} in the date range "
                f"{required_start_date} - {backtest_end_date}. "
                f"Please ensure the data source file exists and contains "
                f"data for this date range."
            )

        self._start_date_data_source = self.data["Datetime"].min()
        self._end_date_data_source = self.data["Datetime"].max()
        self.total_number_of_data_points = len(self.data)

        if self._start_date_data_source is not None and \
                required_start_date < self._start_date_data_source:
            self.number_of_missing_data_points = (
                self._start_date_data_source - required_start_date
            ).total_seconds() / (
                TimeFrame.from_value(self.time_frame).amount_of_minutes * 60
            )

        if self.window_size is not None:
            # Create cache with sliding windows
            self._precompute_sliding_windows(
                data=data,
                window_size=self.window_size,
                time_frame=self.time_frame,
                start_date=backtest_start_date,
                end_date=backtest_end_date
            )

        n_min = TimeFrame.from_value(self.time_frame).amount_of_minutes
        # Assume self.data is a Polars DataFrame with a "Datetime" column
        expected_dates = pl.datetime_range(
            start=required_start_date,
            end=backtest_end_date,
            interval=f"{n_min}m",
            eager=True
        ).to_list()

        actual_dates = self.data["Datetime"].to_list()

        # Find missing dates
        self.missing_data_point_dates = sorted(
            set(expected_dates) - set(actual_dates)
        )

    def get_data(
        self,
        date: datetime = None,
        start_date: datetime = None,
        end_date: datetime = None,
        save: bool = False,
    ) -> Union[pl.DataFrame, pd.DataFrame]:
        """
        Function to retrieve data from the CCXT data provider.
        This function retrieves OHLCV data for a given symbol, time frame,
        and market. It uses the CCXT library to fetch the data and returns
        it in a polars DataFrame format. If pandas is set to True, it
        converts the polars DataFrame to a pandas DataFrame.

        Args:
            date (datetime, optional): The date for which to retrieve the data.
            start_date (datetime): The start date for the data.
            end_date (datetime): The end date for the data.
            save (bool): If True, the data will be saved to the storage path
                if it is not already available. Defaults to False.

        Returns:
            DataFrame: The data for the given symbol and market.
        """

        if self.market is None:
            raise OperationalException(
                "Market is not set. Please set the market "
                "before calling get_data."
            )

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

        if date is not None and self.window_size is not None \
                and self.time_frame is not None:
            start_date = self.create_start_date(
                end_date=date,
                time_frame=self.time_frame,
                window_size=self.window_size
            )
            end_date = date
        else:
            if (end_date is None and start_date is None
                    and self.window_size is None):
                raise OperationalException(
                    "A start date or end date or window size is required "
                    "to retrieve ohlcv data."
                )

            if (start_date is not None and end_date is None
                    and self.window_size is None):
                end_date = datetime.now(tz=timezone.utc)

            if (end_date is not None and start_date is None
                    and self.window_size is None):
                raise OperationalException(
                    "A window size is required when using an end date "
                    "to retrieve ohlcv data."
                )

            if start_date is not None and end_date is None:
                end_date = self.create_end_date(
                    start_date=start_date,
                    time_frame=self.time_frame,
                    window_size=self.window_size
                )

            if end_date is not None and start_date is None \
                    and self.window_size is not None:
                start_date = self.create_start_date(
                    end_date=end_date,
                    time_frame=self.time_frame,
                    window_size=self.window_size
                )

        if start_date is None and end_date is None:
            end_date = datetime.now(tz=timezone.utc)
            start_date = self.create_start_date(
                end_date=end_date,
                time_frame=self.time_frame,
                window_size=self.window_size
            )
        storage_directory = self.get_storage_directory()

        if storage_directory is None:
            if save:
                raise OperationalException(
                    "Storage directory is not set for "
                    "the CCXTOHLCVDataProvider. Make sure to set the "
                    "storage directory in the configuration or "
                    "in the constructor."
                )

            data = self.get_ohlcv(
                symbol=self.symbol,
                time_frame=self.time_frame,
                from_timestamp=start_date,
                market=self.market,
                to_timestamp=end_date
            )
        else:
            # Canonical merge-and-slice cache: only the sub-range(s) not
            # already cached on disk are downloaded. `save` only controls
            # whether newly downloaded data is persisted back to disk.
            data = self._get_or_fetch_data(
                symbol=self.symbol,
                market=self.market,
                time_frame=self.time_frame,
                storage_path=storage_directory,
                start_date=start_date,
                end_date=end_date,
                persist=save,
            )

        if self.pandas:
            data = convert_polars_to_pandas(data)

        return data

    def get_backtest_data(
        self,
        backtest_index_date: datetime,
        backtest_start_date: datetime = None,
        backtest_end_date: datetime = None,
        data_source: DataSource = None
    ) -> None:
        """
        Fetches backtest data for a given datasource

        Args:
            backtest_index_date (datetime): The date for which to fetch
                backtest data.
            backtest_start_date (datetime): The start date for the
                backtest data.
            backtest_end_date (datetime): The end date for the
                backtest data.
            data_source (Optional[Datasource]): The data source for which to
                fetch backtest data. Defaults to None.

        Returns:
            pl.DataFrame: The backtest data for the given datasource.
        """

        if backtest_start_date is not None and \
                backtest_end_date is not None:

            if backtest_start_date < self._start_date_data_source:

                if data_source is not None:
                    raise OperationalException(
                        f"Request data date {backtest_start_date} "
                        f"is before the range of "
                        f"the available data "
                        f"{self._start_date_data_source} "
                        f"- {self._end_date_data_source}."
                        f" for data source {data_source.identifier}."
                        f" Data source file path: "
                        f"{self.get_data_source_file_path()}"
                    )

                raise OperationalException(
                    f"Request data date {backtest_start_date} "
                    f"is before the range of "
                    f"the available data "
                    f"{self._start_date_data_source} "
                    f"- {self._end_date_data_source}."
                    f" Data source file path: "
                    f"{self.get_data_source_file_path()}"
                )

            if backtest_end_date > self._end_date_data_source:

                if data_source is not None:
                    raise OperationalException(
                        f"Request data date {backtest_end_date} "
                        f"is after the range of "
                        f"the available data "
                        f"{self._start_date_data_source} "
                        f"- {self._end_date_data_source}."
                        f" for data source {data_source.identifier}."
                        f" Data source file path: "
                        f"{self.get_data_source_file_path()}"
                    )

                raise OperationalException(
                    f"Request data date {backtest_end_date} "
                    f"is after the range of "
                    f"the available data "
                    f"{self._start_date_data_source} "
                    f"- {self._end_date_data_source}."
                    f" Data source file path: "
                    f"{self.get_data_source_file_path()}"
                )

            data = self.data.filter(
                (pl.col("Datetime") >= backtest_start_date) &
                (pl.col("Datetime") <= backtest_end_date)
            )
        else:
            # If window_size is set, use the precomputed window cache
            if self.window_size is not None and len(self.window_cache) > 0:
                try:
                    data = self.window_cache[backtest_index_date]
                except KeyError:

                    try:
                        # Return the key in the cache that is closest to the
                        # backtest_index_date but not after it.
                        closest_key = min(
                            [k for k in self.window_cache.keys()
                             if k >= backtest_index_date]
                        )
                        data = self.window_cache[closest_key]
                    except ValueError:

                        if data_source is not None:
                            raise OperationalException(
                                "No OHLCV data available for the "
                                f"date: {backtest_index_date} "
                                f"within the prepared backtest data "
                                f"for data source {data_source.identifier}. "
                            )

                        raise OperationalException(
                            "No OHLCV data available for the "
                            f"date: {backtest_index_date} "
                            f"within the prepared backtest data "
                            f"for symbol {self.symbol}. "
                        )
            else:
                # No window cache and no start/end dates -
                # return all data up to backtest_index_date
                if self.data is None or len(self.data) == 0:
                    ds_id = data_source.identifier \
                        if data_source else self.symbol
                    raise OperationalException(
                        "No OHLCV data available for the "
                        f"date: {backtest_index_date} "
                        f"for data source {ds_id}. "
                        "Data has not been loaded."
                    )

                # Filter data up to and including the backtest_index_date
                data = self.data.filter(
                    pl.col("Datetime") <= backtest_index_date
                )

                if len(data) == 0:
                    ds_id = data_source.identifier \
                        if data_source else self.symbol
                    raise OperationalException(
                        "No OHLCV data available for the "
                        f"date: {backtest_index_date} "
                        f"for data source {ds_id}. "
                        f"Data starts at {self.data['Datetime'].min()}."
                    )

        if self.pandas:
            data = convert_polars_to_pandas(data)

        return data

    def get_ohlcv(
        self, symbol, time_frame, from_timestamp, market, to_timestamp=None
    ) -> pl.DataFrame:
        """
        Function to retrieve ohlcv data for a symbol, time frame and market

        Args:
            symbol (str): The symbol to retrieve ohlcv data for
            time_frame: The time frame to retrieve ohlcv data for
            from_timestamp: The start date to retrieve ohlcv data from
            market: The market to retrieve ohlcv data from
            to_timestamp: The end date to retrieve ohlcv data to

        Returns:
            DataFrame: The ohlcv data for the symbol, time frame and market
                in polars DataFrame format
        """
        symbol = symbol.upper()
        market_credential = self.get_credential(market)
        exchange = self.initialize_exchange(market, market_credential)
        time_frame = time_frame.value

        if from_timestamp > to_timestamp:
            raise OperationalException(
                "OHLCV data start date must be before end date"
            )

        if self.config is not None and DATETIME_FORMAT in self.config:
            datetime_format = self.config[DATETIME_FORMAT]
        else:
            datetime_format = CCXT_DATETIME_FORMAT

        if not exchange.has['fetchOHLCV']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality get_ohclvs"
            )

        from_timestamp = exchange.parse8601(
            from_timestamp.strftime(datetime_format)
        )

        if to_timestamp is None:
            to_timestamp = exchange.milliseconds()
        else:
            to_timestamp = exchange.parse8601(
                to_timestamp.strftime(datetime_format)
            )
        data = []

        try:
            while from_timestamp < to_timestamp:
                ohlcv = exchange.fetch_ohlcv(
                    symbol, time_frame, from_timestamp
                )

                if len(ohlcv) > 0:
                    from_timestamp = \
                        ohlcv[-1][0] + \
                        exchange.parse_timeframe(time_frame) * 1000
                else:
                    from_timestamp = to_timestamp

                for candle in ohlcv:
                    datetime_stamp = parser.parse(exchange.iso8601(candle[0]))

                    to_timestamp_datetime = parser.parse(
                        exchange.iso8601(to_timestamp),
                    )

                    if datetime_stamp <= to_timestamp_datetime:
                        datetime_stamp = datetime_stamp \
                            .strftime(datetime_format)

                        data.append(
                            [datetime_stamp] +
                            [float(value) for value in candle[1:]]
                        )

                sleep(exchange.rateLimit / 1000)
        except ccxt.NetworkError as e:
            logger.error(
                f"Network error occurred while fetching OHLCV data for "
                f"{symbol} on {market} with time frame {time_frame}: {e}"
            )
            raise NetworkError(
                "Network error occurred, make sure you have an active "
                "internet connection"
            )

        # Explicit dtypes so an empty `data` list (no candles in range)
        # still yields a typed Datetime column instead of Null.
        schema = {
            "Datetime": pl.Utf8,
            "Open": pl.Float64,
            "High": pl.Float64,
            "Low": pl.Float64,
            "Close": pl.Float64,
            "Volume": pl.Float64,
        }

        # Combine the Series into a DataFrame with given column names
        df = pl.DataFrame(data, schema=schema, orient="row").with_columns(
            pl.col("Datetime").str.to_datetime(time_unit="ms", time_zone="UTC")
        )
        return df

    def create_start_date(self, end_date, time_frame, window_size):
        minutes = TimeFrame.from_value(time_frame).amount_of_minutes
        return end_date - timedelta(minutes=window_size * minutes)

    def create_end_date(self, start_date, time_frame, window_size):
        minutes = TimeFrame.from_value(time_frame).amount_of_minutes
        return start_date + timedelta(minutes=window_size * minutes)

    @staticmethod
    def initialize_exchange(market, market_credential):
        """
        Function to initialize the exchange for the market.

        Args:
            market (str): The market to initialize the exchange for
            market_credential (MarketCredential): The market credential to use
                for the exchange

        Returns:
            Exchange: CCXT exchange client
        """
        market = market.lower()

        if not hasattr(ccxt, market):
            raise OperationalException(
                f"No ccxt exchange for market id {market}"
            )

        exchange_class = getattr(ccxt, market)

        if exchange_class is None:
            raise OperationalException(
                f"No market service found for market id {market}"
            )

        if market_credential is not None:
            # Check the credentials for the exchange
            CCXTOHLCVDataProvider\
                .check_credentials(exchange_class, market_credential)
            exchange = exchange_class({
                'apiKey': market_credential.api_key,
                'secret': market_credential.secret_key,
            })
        else:
            exchange = exchange_class({})
        return exchange

    @staticmethod
    def check_credentials(
        exchange_class, market_credential: MarketCredential
    ):
        """
        Function to check if the credentials are valid for the exchange.

        Args:
            exchange_class: The exchange class to check the credentials for
            market_credential: The market credential to use for the exchange

        Raises:
            OperationalException: If the credentials are not valid

        Returns:
            None
        """
        exchange = exchange_class()
        credentials_info = exchange.requiredCredentials
        market = market_credential.get_market()

        if ('apiKey' in credentials_info
                and credentials_info["apiKey"]
                and market_credential.get_api_key() is None):
            raise OperationalException(
                f"Market credential for market {market}"
                " requires an api key, either"
                " as an argument or as an environment variable"
                f" named as {market.upper()}_API_KEY"
            )

        if ('secret' in credentials_info
                and credentials_info["secret"]
                and market_credential.get_secret_key() is None):
            raise OperationalException(
                f"Market credential for market {market}"
                " requires a secret key, either"
                " as an argument or as an environment variable"
                f" named as {market.upper()}_SECRET_KEY"
            )

    def _canonical_storage_file_name(
        self, symbol: str, market: str, time_frame
    ) -> str:
        """
        Deterministic, date-range-free file name for the single cache
        file that holds all OHLCV data ever downloaded for a given
        (symbol, market, time_frame) combination.
        """
        tf = time_frame.value if hasattr(time_frame, "value") else time_frame
        safe_symbol = symbol.upper().replace('/', '-')
        return f"OHLCV_{safe_symbol}_{market.upper()}_{tf}.csv"

    def _canonical_storage_file_path(
        self, storage_path, symbol: str, market: str, time_frame
    ) -> Union[str, None]:
        if storage_path is None or symbol is None or market is None \
                or time_frame is None:
            return None

        return os.path.join(
            storage_path,
            self._canonical_storage_file_name(symbol, market, time_frame),
        )

    def _read_ohlcv_csv(self, file_path: str) -> Union[pl.DataFrame, None]:
        """
        Reads a single OHLCV CSV file from disk and normalizes its
        Datetime column to a UTC, millisecond-precision datetime, so it
        can be safely merged with other cached/downloaded frames.
        """
        if not os.path.exists(file_path):
            return None

        try:
            data = pl.read_csv(file_path, low_memory=True)
        except Exception as e:
            logger.warning(
                f"Error reading cached OHLCV data from {file_path}: {e}"
            )
            return None

        if "Datetime" not in data.columns:
            logger.warning(
                f"No 'Datetime' column found in {file_path}. "
                f"Available columns: {data.columns}"
            )
            return None

        try:
            # Legacy files (pre canonical cache) were written with an
            # ISO offset (e.g. "...+00:00"); the canonical cache writes
            # a plain UTC string. Try the generic parser first since it
            # handles both, falling back to an explicit-UTC reparse of
            # naive timestamps.
            data = data.with_columns(
                pl.col("Datetime").str.to_datetime(time_zone="UTC")
            )
        except Exception:
            try:
                data = data.with_columns(
                    pl.col("Datetime").str.to_datetime()
                    .dt.replace_time_zone("UTC")
                )
            except Exception as e:
                logger.warning(
                    f"Could not parse Datetime column in {file_path}: {e}"
                )
                return None

        # Normalize to a fixed time unit so cached rows can be safely
        # concatenated with freshly downloaded rows (which use "ms").
        data = data.with_columns(
            pl.col("Datetime").cast(pl.Datetime("ms", "UTC"))
        )

        numeric_columns = [
            column for column in
            ("Open", "High", "Low", "Close", "Volume")
            if column in data.columns
        ]

        if numeric_columns:
            data = data.with_columns(
                [pl.col(c).cast(pl.Float64) for c in numeric_columns]
            )

        self.data_file_path = file_path
        return data.sort("Datetime")

    def _read_legacy_files(
        self, storage_path, symbol: str, market: str, time_frame
    ) -> Union[pl.DataFrame, None]:
        """
        Backward compatibility: before the canonical single-file cache,
        every downloaded window was saved as its own
        "OHLCV_<SYMBOL>_<MARKET>_<TIME_FRAME>_<START>_<END>.csv" file.
        Scans for any such files matching (symbol, market, time_frame)
        and merges them, so pre-existing caches keep working.
        """
        if storage_path is None or not os.path.isdir(storage_path):
            return None

        tf = time_frame.value if hasattr(time_frame, "value") else time_frame
        safe_symbol = symbol.upper().replace('/', '-')
        prefix = f"OHLCV_{safe_symbol}_{market.upper()}_{tf}_"
        matches = [
            os.path.join(storage_path, file_name)
            for file_name in os.listdir(storage_path)
            if file_name.startswith(prefix) and file_name.endswith(".csv")
        ]

        if not matches:
            return None

        frames = [self._read_ohlcv_csv(path) for path in matches]
        return self._merge_ohlcv_frames(frames)

    def _read_canonical_file(
        self, storage_path, symbol: str, market: str, time_frame
    ) -> Union[pl.DataFrame, None]:
        """
        Reads the full canonical cache file for (symbol, market,
        time_frame) from disk, if it exists. Falls back to scanning
        for pre-existing legacy (date-range-suffixed) files. Read-only:
        never writes to disk. Returns None if there is no cached data
        at all yet.
        """
        file_path = self._canonical_storage_file_path(
            storage_path, symbol, market, time_frame
        )

        if file_path is not None and os.path.exists(file_path):
            return self._read_ohlcv_csv(file_path)

        return self._read_legacy_files(
            storage_path, symbol, market, time_frame
        )

    def _write_canonical_file(
        self, storage_path, symbol: str, market: str, time_frame, data
    ) -> None:
        if data is None or len(data) == 0:
            return

        file_path = self._canonical_storage_file_path(
            storage_path, symbol, market, time_frame
        )

        if file_path is None:
            return

        os.makedirs(storage_path, exist_ok=True)
        write_data = data.with_columns(
            pl.col("Datetime").dt.strftime("%Y-%m-%d %H:%M:%S")
        )
        write_data.write_csv(file_path)
        self.data_file_path = file_path

    def _find_missing_ranges(
        self, cached, start_date: datetime, end_date: datetime, time_frame
    ) -> List[tuple]:
        """
        Compares the already-cached range to [start_date, end_date] and
        returns the sub-range(s) that still need to be downloaded. An
        empty list means the request is already fully covered by the
        cache.
        """
        if cached is None or len(cached) == 0:
            return [(start_date, end_date)]

        step = timedelta(
            minutes=TimeFrame.from_value(time_frame).amount_of_minutes
        )
        cached_min = cached["Datetime"].min()
        cached_max = cached["Datetime"].max()
        gaps = []

        if start_date < cached_min:
            gap_end = min(cached_min - step, end_date)
            if start_date <= gap_end:
                gaps.append((start_date, gap_end))

        if end_date > cached_max:
            gap_start = max(cached_max + step, start_date)
            if gap_start <= end_date:
                gaps.append((gap_start, end_date))

        return gaps

    def _merge_ohlcv_frames(
        self, frames: List
    ) -> Union[pl.DataFrame, None]:
        frames = [
            frame for frame in frames if frame is not None and len(frame) > 0
        ]

        if not frames:
            return None

        merged = frames[0]

        for frame in frames[1:]:
            merged = pl.concat([merged, frame], how="vertical_relaxed")

        return merged.unique(subset=["Datetime"], keep="last").sort(
            "Datetime"
        )

    def _get_or_fetch_data(
        self,
        symbol: str,
        market: str,
        time_frame,
        storage_path: str,
        start_date: datetime,
        end_date: datetime,
        persist: bool = True,
    ) -> pl.DataFrame:
        """
        Canonical merge-and-slice cache.

        Loads whatever is already cached on disk for (symbol, market,
        time_frame) — including any pre-existing legacy cache files —
        and downloads only the sub-range(s) not yet covered, instead
        of re-downloading the full requested range every time. If new
        data actually had to be downloaded and `persist` is True, the
        merged result is (re)written to the single canonical cache
        file for this symbol/market/time_frame (also migrating a
        legacy cache file to the canonical format in the process).
        Returns the requested [start_date, end_date] slice.
        """
        cached = self._read_canonical_file(
            storage_path, symbol, market, time_frame
        )
        gaps = self._find_missing_ranges(
            cached, start_date, end_date, time_frame
        )

        if not gaps:
            merged = cached
        else:
            downloaded = [
                self.get_ohlcv(
                    symbol=symbol,
                    time_frame=TimeFrame.from_value(time_frame),
                    from_timestamp=gap_start,
                    market=market,
                    to_timestamp=gap_end,
                )
                for gap_start, gap_end in gaps
            ]
            merged = self._merge_ohlcv_frames([cached] + downloaded)

            if persist:
                self._write_canonical_file(
                    storage_path, symbol, market, time_frame, merged
                )

        if merged is None or len(merged) == 0:
            return merged

        return merged.filter(
            (pl.col("Datetime") >= start_date)
            & (pl.col("Datetime") <= end_date)
        )

    def _get_data_from_storage(
        self,
        storage_path,
        symbol: str,
        market: str,
        time_frame,
        start_date: datetime,
        end_date: datetime,
    ) -> Union[pl.DataFrame, None]:
        """
        Read-only cache lookup: returns the requested [start_date,
        end_date] slice only if the canonical cache file already fully
        covers it. Returns None otherwise (no network access, no
        writes).
        """
        cached = self._read_canonical_file(
            storage_path, symbol, market, time_frame
        )

        if cached is None:
            return None

        cached_min = cached["Datetime"].min()
        cached_max = cached["Datetime"].max()

        if cached_min is None or cached_min > start_date \
                or cached_max is None or cached_max < end_date:
            return None

        data = cached.filter(
            (pl.col("Datetime") >= start_date)
            & (pl.col("Datetime") <= end_date)
        )

        if len(data) == 0:
            return None

        return data

    def _precompute_sliding_windows(
        self,
        data,
        window_size: int,
        time_frame: TimeFrame,
        start_date: datetime,
        end_date: datetime
    ) -> None:
        """
        Precompute all sliding windows for fast retrieval in backtest mode.

        A sliding window is calculated as a subset of the data. It will
        take for each timestamp in the data a window of size `window_size`
        and stores it in a cache with the last timestamp of the window.

        So if the window size is 200, the first window will be
        the first 200 rows of the data, the second window will be
        the rows 1 to 200, the third window will be the rows
        2 to 201, and so on until the last window which will be
        the last 200 rows of the data.

        Args:
            data (pl.DataFrame): The data to precompute the sliding
                windows for.
            window_size (int): The size of the sliding window to precompute.
            start_date (datetime, optional): The start date for the sliding
                windows.
            end_date (datetime, optional): The end date for the sliding
                windows.

        Returns:
            None
        """
        self.window_cache = {}
        timestamps = data["Datetime"].to_list()
        # Only select the entries after the start date
        timestamps = [
            ts for ts in timestamps if start_date <= ts <= end_date
        ]

        # Create sliding windows of size <window_size> for each timestamp
        # in the data with the given the time frame and window size
        for timestamp in timestamps:
            # Use timestamp as key
            self.window_cache[timestamp] = data.filter(
                (data["Datetime"] <= timestamp) &
                (data["Datetime"] >= timestamp - timedelta(
                    minutes=time_frame.amount_of_minutes * window_size
                ))
            )

        # Make sure the end datetime of the backtest is included in the
        # sliding windows cache
        if end_date not in self.window_cache:
            self.window_cache[end_date] = data[-window_size:]

    def get_storage_directory(self) -> Union[str, None]:
        """
        Get the storage directory for the OHLCV data provider.

        Returns:
            Union[str, None]: The storage directory path if set,
                otherwise None.
        """

        if self.storage_directory is not None:
            return self.storage_directory

        if self.config is not None:
            resource_directory = self.config.get(RESOURCE_DIRECTORY)
            data_directory_name = self.config.get(DATA_DIRECTORY)
            return os.path.join(resource_directory, data_directory_name)

        return None

    def copy(self, data_source) -> "CCXTOHLCVDataProvider":
        """
        Returns a copy of the CCXTOHLCVDataProvider instance based on a
        given data source. The data source is previously matched
        with the 'has_data' method. Then a new instance of the data
        provider must be registered in the framework so that each
        data source has its own instance of the data provider.

        Args:
            data_source (DataSource): The data source specification that
                matches a data provider.

        Returns:
            DataProvider: A new instance of the data provider with the same
                configuration.
        """
        # Check that the data source has the required attributes set
        # for usage with CCXT data providers

        if data_source.market is None or data_source.market == "":
            raise OperationalException(
                "DataSource has not `market` attribute specified, "
                "please specify the market attribute in the "
                "data source specification before using the "
                "ccxt OHLCV data provider"
            )

        if data_source.time_frame is None or data_source.time_frame == "":
            raise OperationalException(
                "DataSource has not `time_frame` attribute specified, "
                "please specify the time_frame attribute in the "
                "data source specification before using the "
                "ccxt OHLCV data provider"
            )

        if data_source.symbol is None or data_source.symbol == "":
            raise OperationalException(
                "DataSource has not `symbol` attribute specified, "
                "please specify the symbol attribute in the "
                "data source specification before using the "
                "ccxt OHLCV data provider"
            )

        storage_path = data_source.storage_path

        if storage_path is None:
            storage_path = self.get_storage_directory()

        provider = CCXTOHLCVDataProvider(
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
        provider.missing_data_point_dates = \
            self.missing_data_point_dates
        provider._start_date_data_source = \
            self._start_date_data_source
        provider._end_date_data_source = \
            self._end_date_data_source
        provider.data_file_path = self.data_file_path
        return provider

    def get_number_of_data_points(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> int:

        """
        Returns the number of data points available between the given
        start and end dates.

        Args:
            start_date (datetime): The start date for checking missing data.
            end_date (datetime): The end date for checking missing data.

        Returns:
            int: The number of available data points between the given
                start and end dates.
        """
        available_dates = [
            date for date in self.data["Datetime"].to_list()
            if start_date <= date <= end_date
        ]
        return len(available_dates)

    def get_missing_data_dates(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> List[datetime]:
        """
        Returns a list of dates for which data is missing between the
        given start and end dates.

        Args:
            start_date (datetime): The start date for checking missing data.
            end_date (datetime): The end date for checking missing data.

        Returns:
            List[datetime]: A list of dates for which data is missing
                between the given start and end dates.
        """
        missing_dates = [
            date for date in self.missing_data_point_dates
            if start_date <= date <= end_date
        ]
        return missing_dates

    def get_data_source_file_path(self) -> Union[str, None]:
        """
        Get the file path of the data source if stored in local storage.

        Returns:
            Union[str, None]: The file path of the data source if stored
                locally, otherwise None.
        """
        return self.data_file_path


class CCXTTickerDataProvider(DataProvider):
    """
    Data provider for ticker data using the CCXT library.

    Fetches real-time ticker data (bid, ask, last price, volume, etc.)
    for a given symbol and market via CCXT's fetch_ticker API.

    In backtest mode, ticker data is derived from OHLCV data
    (handled by the DataProviderService fallback), so this provider
    only serves live/non-backtest use cases.
    """
    data_type = DataType.TICKER
    data_provider_identifier = "ccxt_ticker_data_provider"

    def __init__(
        self,
        symbol: str = None,
        market: str = None,
        data_provider_identifier: str = None,
        config=None
    ):
        if data_provider_identifier is None:
            data_provider_identifier = self.data_provider_identifier

        super().__init__(
            symbol=symbol,
            market=market,
            data_provider_identifier=data_provider_identifier,
            config=config
        )

    def has_data(
        self,
        data_source: DataSource,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> bool:
        data_type = data_source.data_type
        market = data_source.market
        symbol = data_source.symbol

        if not DataType.TICKER.equals(data_type):
            return False

        if market is None:
            market = "binance"

        try:
            market = market.lower()
            exchange_class = getattr(ccxt, market)
            exchange = exchange_class()
            symbols = list(exchange.load_markets().keys())
            return symbol in symbols
        except ccxt.NetworkError:
            return False
        except Exception as e:
            logger.error(e)
            return False

    def prepare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date,
        fill_missing_data: bool = False,
        show_progress: bool = False,
    ) -> None:
        # Ticker backtest data is derived from OHLCV by the
        # DataProviderService fallback — nothing to prepare here.
        pass

    def get_backtest_data(
        self,
        backtest_index_date: datetime,
        backtest_start_date: datetime = None,
        backtest_end_date: datetime = None,
        data_source: DataSource = None,
    ):
        # Backtest ticker data is handled by DataProviderService
        # falling back to OHLCV data.
        return None

    def get_data(
        self,
        date: datetime = None,
        start_date: datetime = None,
        end_date: datetime = None,
        save: bool = False,
    ) -> dict:
        if self.market is None:
            raise OperationalException(
                "Market is not set. Please set the market "
                "before calling get_data."
            )

        if self.symbol is None:
            raise OperationalException(
                "Symbol is not set. Please set the symbol "
                "before calling get_data."
            )

        market_credential = self.get_credential(self.market)
        exchange = CCXTOHLCVDataProvider.initialize_exchange(
            self.market, market_credential
        )
        ticker = exchange.fetch_ticker(self.symbol)

        return {
            "symbol": self.symbol,
            "market": self.market,
            "datetime": ticker.get("datetime"),
            "high": ticker.get("high"),
            "low": ticker.get("low"),
            "bid": ticker.get("bid"),
            "ask": ticker.get("ask"),
            "open": ticker.get("open"),
            "close": ticker.get("close"),
            "last": ticker.get("last"),
            "volume": ticker.get("baseVolume"),
        }

    def copy(self, data_source: DataSource) -> "CCXTTickerDataProvider":
        if data_source.market is None or data_source.market == "":
            raise OperationalException(
                "DataSource has no `market` attribute specified. "
                "Please specify the market attribute in the data source "
                "specification before using the CCXT ticker data provider."
            )

        if data_source.symbol is None or data_source.symbol == "":
            raise OperationalException(
                "DataSource has no `symbol` attribute specified. "
                "Please specify the symbol attribute in the data source "
                "specification before using the CCXT ticker data provider."
            )

        return CCXTTickerDataProvider(
            symbol=data_source.symbol,
            market=data_source.market,
            data_provider_identifier=data_source.data_provider_identifier,
            config=self.config,
        )

    def get_number_of_data_points(
        self, start_date: datetime, end_date: datetime
    ) -> int:
        # Ticker data is a single point-in-time snapshot
        return 1

    def get_missing_data_dates(
        self, start_date: datetime, end_date: datetime
    ) -> list:
        # No stored data to have gaps in
        return []

    def get_data_source_file_path(self):
        # Ticker data is not file-based
        return None
