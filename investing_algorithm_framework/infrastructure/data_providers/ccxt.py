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
    RESOURCE_DIRECTORY, CCXT_DATETIME_FORMAT, DATA_DIRECTORY, \
    DATETIME_FORMAT_FILE_NAME

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
                storage_path=data_source.storage_path,
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
    ) -> None:
        """
        Prepares backtest data for a given symbol and date range.

        Args:
            backtest_start_date (datetime): The start date for the
                backtest data.
            backtest_end_date (datetime): The end date for the
                backtest data.

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

        # Check if the data source is already available in the storage path
        data = self._get_data_from_storage(
            symbol=self.symbol,
            market=self.market,
            time_frame=self.time_frame,
            storage_path=storage_directory_path,
            start_date=required_start_date,
            end_date=backtest_end_date
        )

        if data is None:
            # Disable pandas if it is set to True, because logic
            # depends on polars DataFrame
            has_pandas_flag = self.pandas
            self.pandas = False

            # If the data is not available in the storage path,
            # retrieve it from the CCXT data provider
            data = self.get_data(
                start_date=required_start_date,
                end_date=backtest_end_date,
                save=True,
            )

            self.pandas = has_pandas_flag

        self.data = data
        self._start_date_data_source = self.data["Datetime"].min()
        self._end_date_data_source = self.data["Datetime"].max()
        self.total_number_of_data_points = len(self.data)

        if required_start_date < self._start_date_data_source:
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
        data = self._get_data_from_storage(
            symbol=self.symbol,
            market=self.market,
            time_frame=self.time_frame,
            storage_path=self.get_storage_directory(),
            start_date=start_date,
            end_date=end_date
        )

        if data is None:
            data = self.get_ohlcv(
                symbol=self.symbol,
                time_frame=self.time_frame,
                from_timestamp=start_date,
                market=self.market,
                to_timestamp=end_date
            )

            if save:
                storage_directory = self.get_storage_directory()

                if storage_directory is None:
                    raise OperationalException(
                        "Storage directory is not set for "
                        "the CCXTOHLCVDataProvider. Make sure to set the "
                        "storage directory in the configuration or "
                        "in the constructor."
                    )

                self.save_data_to_storage(
                    symbol=self.symbol,
                    market=self.market,
                    time_frame=self.time_frame,
                    start_date=start_date,
                    end_date=end_date,
                    data=data,
                    storage_directory_path=storage_directory
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

        # Predefined column names
        col_names = ["Datetime", "Open", "High", "Low", "Close", "Volume"]

        # Combine the Series into a DataFrame with given column names
        df = pl.DataFrame(data, schema=col_names, orient="row").with_columns(
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

    def save_data_to_storage(
        self,
        symbol: str,
        market: str,
        time_frame: TimeFrame,
        start_date: datetime,
        end_date: datetime,
        data: pl.DataFrame,
        storage_directory_path: str,
    ):
        """
        Function to save data to the storage path.

        Args:
            symbol (str): The symbol for which the data is saved.
            market (str): The market for which the data is saved.
            time_frame (TimeFrame): The time frame for which the data is saved.
            data (pl.DataFrame): The data to save.
            storage_directory_path (str): The path to the storage directory.
            start_date (datetime): The start date for the data.
            end_date (datetime): The end date for the data.

        Returns:
            None
        """
        if storage_directory_path is None:
            raise OperationalException(
                "Storage path is not set. Please set the storage path "
                "before saving data."
            )

        if not os.path.isdir(storage_directory_path):
            os.makedirs(storage_directory_path)

        filename = self._create_filename(
            symbol=symbol,
            market=market,
            time_frame=time_frame.value,
            start_date=start_date,
            end_date=end_date
        )
        storage_path = os.path.join(storage_directory_path, filename)
        if os.path.exists(storage_path):
            os.remove(storage_path)

        # Create the file
        if not os.path.exists(storage_path):
            with open(storage_path, 'w'):
                pass

        data.write_csv(storage_path)

    def _create_filename(
        self,
        symbol: str,
        market: str,
        time_frame: str,
        start_date: datetime,
        end_date: datetime
    ) -> str:
        """
        Creates a filename for the data file based on the parameters.
        The date format is YYYYMMDDHH for both start and end dates.

        Args:
            symbol (str): The symbol of the data.
            market (str): The market of the data.
            time_frame (str): The time frame of the data.
            start_date (datetime): The start date of the data.
            end_date (datetime): The end date of the data.

        Returns:
            str: The generated filename.
        """
        datetime_format = self.config[DATETIME_FORMAT_FILE_NAME]
        symbol = symbol.upper().replace('/', '-')
        start_date_str = start_date.strftime(datetime_format)
        end_date_str = end_date.strftime(datetime_format)
        filename = (
            f"OHLCV_{symbol}_{market.upper()}_{time_frame}_{start_date_str}_"
            f"{end_date_str}.csv"
        )
        return filename

    def _get_data_from_storage(
        self,
        storage_path,
        symbol: str,
        market: str,
        time_frame: TimeFrame,
        start_date: datetime,
        end_date: datetime,
    ) -> Union[pl.DataFrame, None]:
        """
        Helper function to retrieve the data from the storage path if
        it exists. If the data does not exist, it returns None.
        """
        data = None
        if storage_path is None:
            return None

        # Loop through all files in the data storage path
        if not os.path.isdir(storage_path):
            logger.error(
                f"Storage path {storage_path} does not exist or is not a "
                "directory."
            )
            return None

        for file_name in os.listdir(storage_path):
            if file_name.startswith("OHLCV_") and file_name.endswith(".csv"):

                try:
                    data_source_spec = self.\
                        _get_data_source_specification_from_file_name(
                            file_name
                        )

                    if data_source_spec is None:
                        continue

                    if data_source_spec.symbol.upper() == symbol.upper() and \
                        data_source_spec.market.upper() == market.upper() and \
                            data_source_spec.time_frame.equals(time_frame):

                        # Check if the data source specification matches
                        # the start and end date if its specified
                        if (data_source_spec.start_date is not None and
                            data_source_spec.end_date is not None and
                                (data_source_spec.start_date <= start_date
                                 and data_source_spec.end_date >= end_date)):

                            # If the data source specification matches,
                            # read the file
                            file_path = os.path.join(storage_path, file_name)
                            self.data_file_path = file_path

                            # Read CSV as-is first
                            data = pl.read_csv(file_path, low_memory=True)

                            # Check what columns we have
                            if "Datetime" in data.columns:
                                # Try to parse the datetime column
                                try:
                                    # Try the ISO format with timezone first
                                    data = data.with_columns(
                                        pl.col("Datetime").str.to_datetime(
                                            format="%Y-%m-%dT%H:%M:%S%.f%z",
                                            time_zone="UTC"
                                        )
                                    )
                                except Exception as e1:
                                    try:
                                        # Fallback: let Polars infer the format
                                        data = data.with_columns(
                                            pl.col("Datetime").str.to_datetime(
                                                time_zone="UTC"
                                            )
                                        )
                                    except Exception as e2:
                                        logger.warning(
                                            f"Could not parse Datetime "
                                            f"column in {file_name}: "
                                            f"Format error: {str(e1)}, "
                                            f"Infer error: {str(e2)}"
                                        )
                                        continue
                            else:
                                logger.warning(
                                    f"No 'Datetime' column "
                                    f"found in {file_name}. "
                                    f"Available columns: {data.columns}"
                                )
                                continue

                            # Filter by date range
                            data = data.filter(
                                (pl.col("Datetime") >= start_date) &
                                (pl.col("Datetime") <= end_date)
                            )
                            break

                except Exception as e:
                    logger.warning(
                        f"Error reading data from {file_name}: {str(e)}"
                    )
                    continue

        return data

    def _get_data_source_specification_from_file_name(
        self, file_name: str
    ) -> Union[DataSource, None]:
        """
        Extracts the data source specification from the OHLCV data filename.
        Given that the file name is in the format:

        "OHLCV_<SYMBOL>_<MARKET>_<TIME_FRAME>_<START_DATE>_<END_DATE>.csv",
        this function extracts all attributes and returns a DataSource object.
        This object can then later be used to compare it to the datasource
        object that is passed to the get_data method.

        Args:
            file_name (str): The file name from which to extract the DataSource

        Returns:
            DataSource: The extracted data source specification.
        """

        try:
            parts = file_name.split('_')

            if len(parts) < 3:
                return None

            data_type = parts[0].upper()
            symbol = parts[1].upper().replace('-', '/')
            market = parts[2].upper()
            time_frame_str = parts[3]
            start_date_str = parts[4]
            end_date_str = parts[5].replace('.csv', '')
            return DataSource(
                data_type=DataType.from_string(data_type),
                symbol=symbol,
                market=market,
                time_frame=TimeFrame.from_string(time_frame_str),
                start_date=parser.parse(
                    start_date_str
                ).replace(tzinfo=timezone.utc),
                end_date=parser.parse(
                    end_date_str
                ).replace(tzinfo=timezone.utc)
            )
        except ValueError:
            logger.info(
                f"Could not extract data source attributes from "
                f"file name: {file_name}. "
                f"Expected format 'OHLCV_<SYMBOL>_<MARKET>_<TIME_FRAME>_"
                f"<START_DATE>_<END_DATE>.csv."
            )
            return None

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

        return CCXTOHLCVDataProvider(
            symbol=data_source.symbol,
            time_frame=data_source.time_frame,
            market=data_source.market,
            window_size=data_source.window_size,
            data_provider_identifier=data_source.data_provider_identifier,
            storage_directory=storage_path,
            config=self.config,
            pandas=data_source.pandas,
        )

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
