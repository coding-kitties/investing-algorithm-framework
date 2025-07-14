import logging
import os.path
from datetime import datetime, timedelta, timezone
from time import sleep
from typing import Union

import ccxt
import pandas as pd
import polars as pl
from dateutil import parser

from investing_algorithm_framework.domain import OperationalException, \
    DATETIME_FORMAT, DataProvider, convert_polars_to_pandas, \
    NetworkError, TimeFrame, MarketCredential, DataType, DataSource

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
        symbol: str,
        time_frame: str,
        market: str,
        window_size=None,
        data_provider_identifier: str = None,
        storage_directory = None
    ):
        """
        Initialize the CCXT OHLCV Data Provider.

        Args:
            symbol (str): The symbol for which the data is provided.
            time_frame (str): The time frame for the data.
            market (str, optional): The market for the data. Defaults to None.
            window_size (int, optional): The window size for the data.
                Defaults to None.
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
            storage_path=storage_directory,
            data_provider_identifier=data_provider_identifier
        )
        self._start_date_data_source = None
        self._end_date_data_source = None
        self._columns = ["Datetime", "Open", "High", "Low", "Close", "Volume"]
        self.window_cache = {}
        self.data = None

    def has_data(
        self,
        data_source: DataSource,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> bool:
        """
        Implementation of the has_data method to check if
        the data provider has data for the given data source.

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

        if not DataType.OHLCV.equals(data_type):
            return False

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
            raise NetworkError(
                "Network error occurred, make sure you have "
                "an active internet connection"
            )

        except Exception as e:
            logger.error(e)
            return False

    def prepare_backtest_data(
        self,
        data_source: DataSource,
        backtest_start_date,
        backtest_end_date,
    ) -> None:
        """
        Prepares backtest data for a given symbol and date range.

        Args:
            data_source (DataSource): The data source specification that
                matches a data provider.
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

        if backtest_start_date < self._start_date_data_source:
            raise OperationalException(
                f"Backtest start date {backtest_start_date} is before the "
                f"start date {self._start_date_data_source}"
            )

        if backtest_end_date > self._end_date_data_source:
            raise OperationalException(
                f"Backtest end date {backtest_end_date} is after the "
                f"end date {self._end_date_data_source}"
            )

        # There must be at least backtest_start_date - window_size * time_frame
        # data available to create a sliding window.
        required_start_date = backtest_start_date - \
            timedelta(
              minutes=TimeFrame.from_value(
                  data_source.time_frame)
                      .amount_of_minutes * data_source.window_size
            )

        if required_start_date < self._start_date_data_source:
            raise OperationalException(
                f"Not enough data available for data source {data_source} "
                f"Data earlier then {required_start_date} is required, but only "
                f"{self._start_date_data_source} is available."
            )

        # Check if the data source is already available in the storage path
        data = self._get_data_from_storage(
            storage_path=self.storage_path,
            data_source=data_source
        )

        if data is None:
            # If the data is not available in the storage path,
            # retrieve it from the CCXT data provider
            data = self.get_data(
                data_source=data_source,
                start_date=required_start_date,
                end_date=backtest_end_date
            )

        # Create cache with sliding windows
        self._precompute_sliding_windows(
            window_size=data_source.window_size,
            start_date=backtest_start_date,
            end_date=backtest_end_date
        )

    def get_data(
        self,
        data_source: DataSource,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> Union[pl.DataFrame, pd.DataFrame]:
        """
        Function to retrieve data from the CCXT data provider.
        This function retrieves OHLCV data for a given symbol, time frame,
        and market. It uses the CCXT library to fetch the data and returns
        it in a polars DataFrame format. If pandas is set to True, it
        converts the polars DataFrame to a pandas DataFrame.

        Args:
            data_source (DataSource): The data source specification that
                matches a data provider.
            start_date (datetime): The start date for the data.
            end_date (datetime): The end date for the data.

        Returns:
            DataFrame: The data for the given symbol and market.
        """
        market = data_source.market
        start_date = data_source.start_date
        end_date = data_source.end_date
        symbol = data_source.symbol
        time_frame = data_source.time_frame

        if market is None:
            market = self.market

        if market is None:
            raise OperationalException(
                "Market is not set. Please set the market "
                "before calling get_data."
            )

        if symbol is None:
            raise OperationalException(
                "Symbol is not set. Please set the symbol "
                "before calling get_data."
            )

        if time_frame is None:
            raise OperationalException(
                "Time frame is not set. Please set the time frame "
                "before requesting ohlcv data."
            )

        if end_date is None and start_date is None and data_source.window_size is None:
            raise OperationalException(
                "A start date or end date or window size is required "
                "to retrieve ohlcv data."
            )

        if (start_date is not None and end_date is None
                and data_source.window_size is None):
            raise OperationalException(
                "A window size is required when using a start date "
                "to retrieve ohlcv data."
            )

        if (end_date is not None and start_date is None
                and data_source.window_size is None):
            raise OperationalException(
                "A window size is required when using an end date "
                "to retrieve ohlcv data."
            )

        if start_date is not None and end_date is None:
            end_date = self.create_end_date(
                start_date=start_date,
                time_frame=time_frame,
                window_size=data_source.window_size
            )

        elif end_date is not None and start_date is None:
            start_date = self.create_start_date(
                end_date=end_date,
                time_frame=time_frame,
                window_size=data_source.window_size
            )

        data = self._retrieve_data_from_storage(
            storage_path=self.storage_path,
            symbol=symbol,
            market=market,
            time_frame=time_frame,
            start_date=start_date,
            end_date=end_date
        )

        if data is None:
            data = self.get_ohlcv(
                symbol=symbol,
                time_frame=time_frame,
                from_timestamp=start_date,
                market=market,
                to_timestamp=end_date
            )

        if data_source.save:
            self.save_data_to_storage(
                symbol=symbol,
                market=market,
                start_date=start_date,
                end_date=end_date,
                time_frame=time_frame,
                data=data,
                storage_path=self.storage_path
            )

        if data_source.pandas:
            data = convert_polars_to_pandas(data)

        return data

    def get_backtest_data(
        self,
        data_source: DataSource,
        backtest_index_date: datetime,
        backtest_start_date: datetime = None,
        backtest_end_date: datetime = None
    ) -> None:
        """
        Fetches backtest data for a given datasource

        Args:
            data_source (DataSource): The data source specification that
                matches a data provider.
            backtest_index_date (datetime): The date for which to fetch
                backtest data.
            backtest_start_date (datetime): The start date for the
                backtest data.
            backtest_end_date (datetime): The end date for the
                backtest data.

        Returns:
            pl.DataFrame: The backtest data for the given datasource.
        """
        return self.window_cache[backtest_index_date]

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

        if from_timestamp > to_timestamp:
            raise OperationalException(
                "OHLCV data start date must be before end date"
            )

        if self.config is not None and "DATETIME_FORMAT" in self.config:
            datetime_format = self.config["DATETIME_FORMAT"]
        else:
            datetime_format = DATETIME_FORMAT

        if not exchange.has['fetchOHLCV']:
            raise OperationalException(
                f"Market service {market} does not support "
                f"functionality get_ohclvs"
            )

        from_time_stamp = exchange.parse8601(
            from_timestamp.strftime(datetime_format)
        )

        if to_timestamp is None:
            to_timestamp = exchange.milliseconds()
        else:
            to_timestamp = exchange.parse8601(
                to_timestamp.strftime(datetime_format)
            )
        data = []

        while from_time_stamp < to_timestamp:
            ohlcv = exchange.fetch_ohlcv(symbol, time_frame, from_time_stamp)

            if len(ohlcv) > 0:
                from_time_stamp = \
                    ohlcv[-1][0] + exchange.parse_timeframe(time_frame) * 1000
            else:
                from_time_stamp = to_timestamp

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

        # Predefined column names
        col_names = ["Datetime", "Open", "High", "Low", "Close", "Volume"]

        # Combine the Series into a DataFrame with given column names
        df = pl.DataFrame(data, schema=col_names, orient="row")
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

    def _retrieve_data_from_storage(
        self,
        storage_path: str,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> pl.DataFrame | None:
        """
        Function to retrieve data from the storage path.

        Args:
            storage_path (str): The path to the storage.
            symbol (str): The symbol to retrieve data for.
            market (str): The market to retrieve data from.
            time_frame (str): The time frame to retrieve data for.
            start_date (datetime): The start date to retrieve data from.
            end_date (datetime): The end date to retrieve data to.

        Returns:
            pl.DataFrame: The retrieved data in Polars DataFrame format.
        """

        if not os.path.isdir(storage_path):
            return None

        file_name = self._create_filename(
            symbol=symbol,
            market=market,
            time_frame=time_frame,
            start_date=start_date,
            end_date=end_date
        )

        file_path = os.path.join(storage_path, file_name)

        if os.path.exists(file_path):
            try:
                data = pl.read_csv(file_path).with_columns(
                    pl.col("Datetime").str.strptime(
                        pl.Datetime("us", "UTC"),
                        # microsecond precision, with UTC tz
                        fmt="%+"
                    )
                )
                return data
            except Exception as e:
                logger.error(
                    f"Error reading data from {file_path}: {e}"
                )
                return None

        return None

    def save_data_to_storage(
        self,
        symbol,
        market,
        start_date: datetime,
        end_date: datetime,
        time_frame: str,
        data: pl.DataFrame,
        storage_path: str,
    ):
        """
        Function to save data to the storage path.

        Args:
            data (pl.DataFrame): The data to save.
            storage_path (str): The path to the storage.

        Returns:
            None
        """
        if storage_path is None:
            raise OperationalException(
                "Storage path is not set. Please set the storage path "
                "before saving data."
            )

        if not os.path.isdir(storage_path):
            os.makedirs(storage_path)

        symbol = symbol.upper().replace('/', '_')
        filename = self._create_filename(
            symbol=symbol,
            market=market,
            time_frame=time_frame,
            start_date=start_date,
            end_date=end_date
        )
        storage_path = os.path.join(storage_path, filename)
        if os.path.exists(storage_path):
            os.remove(storage_path)

        # Create the file
        if not os.path.exists(storage_path):
            with open(storage_path, 'w'):
                pass

        data.write_csv(storage_path)

    @staticmethod
    def _create_filename(
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
        symbol = symbol.upper().replace('/', '_')
        start_date_str = start_date.strftime('%Y%m%d%H')
        end_date_str = end_date.strftime('%Y%m%d%H')
        filename = (
            f"{symbol}_{market}_{time_frame}_{start_date_str}_"
            f"{end_date_str}.csv"
        )
        return filename

    def _get_data_from_storage(
        self, storage_path, data_source
    ) -> Union[pl.DataFrame, None]:
        """
        Helper function to retrieve the data from the storage path if
        it exists. If the data does not exist, it returns None.

        Args:
            storage_path (str): The path to the storage.
            data_source (DataSource): The data source specification that
                matches a data provider.

        Returns:
            Union[pl.DataFrame, None]: The data from the storage path as a
                Polars DataFrame, or None if the data does not exist.
        """

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
                    data_source_spec = self._get_data_source_specification_from_file_name(
                        file_name
                    )

                    if data_source_spec.equals(
                        data_source, exclude=["start_date", "end_date"]
                    ):
                        # Check if the data source specification matches
                        # the start and end date if its specified
                        if data_source.start_date is not None and \
                            data_source.end_date is not None and \
                            data_source.start_date < data_source_spec\
                                .start_date \
                            and data_source.end_date > data_source_spec\
                                .end_date:
                                continue

                        # If the data source specification matches,
                        # read the file
                        file_path = os.path.join(storage_path, file_name)
                        data = pl.read_csv(file_path).with_columns(
                            pl.col("Datetime").str.strptime(
                                pl.Datetime("us", "UTC"),
                                fmt="%+"
                            )
                        )

                        if data_source.start_date is not None and \
                            data_source.end_date is not None:
                            data = data.filter(
                                (pl.col("Datetime") >= data_source.start_date) &
                                (pl.col("Datetime") <= data_source.end_date)
                            )
                            return data
                except Exception as e:
                    logger.warning(e)
                    continue

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

            symbol = parts[1].upper().replace('-', '/')
            market = parts[2].upper()
            time_frame_str = parts[3]
            start_date_str = parts[4]
            end_date_str = parts[5].replace('.csv', '')

            return DataSource(
                symbol=symbol,
                market=market,
                time_frame=TimeFrame.from_string(time_frame_str),
                start_date=datetime.strptime(
                    start_date_str, '%Y-%m-%d-%H-%M'
                ).replace(tzinfo=timezone.utc),
                end_date=datetime.strptime(
                    end_date_str, '%Y-%m-%d-%H-%M'
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
        window_size: int,
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
            window_size (int): The size of the sliding window to precompute.
            start_date (datetime, optional): The start date for the sliding
                windows.
            end_date (datetime, optional): The end date for the sliding
                windows.

        Returns:
            None
        """
        self.window_cache = {}
        timestamps = self.data["Datetime"].to_list()

        # Only select the entries after the start date
        timestamps = [
            ts for ts in timestamps
            if start_date <= ts <= end_date
        ]

        # Create sliding windows of size <window_size> for each timestamp
        # in the data with the given the time frame and window size
        for timestamp in timestamps:
            # Use timestamp as key
            self.window_cache[timestamp] = self.data.filter(
                (self.data["Datetime"] <= timestamp) &
                (self.data["Datetime"] >= timestamp - timedelta(
                    minutes=self.time_frame.amount_of_minutes * window_size
                ))
            )
