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
    DATETIME_FORMAT, DataProvider, TradingDataType, convert_polars_to_pandas, \
    NetworkError, TimeFrame, MarketCredential

logger = logging.getLogger("investing_algorithm_framework")


class CCXTDataProvider(DataProvider):
    """
    """
    backtest_data_directory = None
    backtest_data_end_date = None
    total_minutes_time_frame = None
    column_names = ["Datetime", "Open", "High", "Low", "Close", "Volume"]

    def __init__(
        self,
        data_type: str = None,
        market=None,
        symbol=None,
        time_frame=None,
        window_size=None,
        priority=1
    ):
        super().__init__(
            data_type=data_type,
            symbol=symbol,
            time_frame=time_frame,
            window_size=window_size,
            priority=priority
        )

        self.market = market
        self.data = None
        self._start_date_data_source = None
        self._end_date_data_source = None
        self.backtest_end_index = self.window_size
        self.backtest_start_index = 0
        self.window_cache = {}

    def initialize_exchange(self, market, market_credential):
        """
        Initializes the exchange for the given market.

        Args:
            market (str): The market to initialize the exchange for.
            market_credential (MarketCredential): MarketCredential - the market

        Returns:
            Instance of the exchange class.
        """

        market = market.lower()
        if not hasattr(ccxt, market):
            raise OperationalException(
                f"No exchange found for market id {market}"
            )

        exchange_class = getattr(ccxt, market)

        if exchange_class is None:
            raise OperationalException(
                f"No exchange found for market id {market}"
            )

        if market_credential is not None:
            exchange = exchange_class({
                'apiKey': market_credential.api_key,
                'secret': market_credential.secret_key,
            })
        else:
            exchange = exchange_class({})

        return exchange

    def pre_pare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        window_size=None
    ) -> None:
        pass

    def get_backtest_data(
        self,
        date: datetime = None,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        backtest_start_date: datetime = None,
        backtest_end_date: datetime = None,
        window_size=None,
        pandas=False
    ) -> None:
        pass

    def has_data(
        self,
        data_type: str = None,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        window_size=None,
    ) -> bool:

        if TradingDataType.CUSTOM.equals(data_type):
            raise OperationalException(
                "Custom data type is not supported for CCXTOHLCVDataProvider"
            )

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

        except Exception:
            return False

    def get_data(
        self,
        data_type: str = None,
        date: datetime = None,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        storage_path=None,
        window_size=None,
        pandas=False,
    ):

        if market is None:
            market = self.market

        if market is None:
            raise OperationalException(
                "Market is not set. Please set the market "
                "before calling get_data."
            )

        if symbol is None:
            symbol = self.symbol

        if symbol is None:
            raise OperationalException(
                "Symbol is not set. Please set the symbol "
                "before calling get_data."
            )

        if data_type is None:
            data_type = self.data_type

        if TradingDataType.OHLCV.equals(data_type):

            if time_frame is None:
                time_frame = self.time_frame

            if time_frame is None:
                raise OperationalException(
                    "Time frame is not set. Please set the time frame "
                    "before requesting ohlcv data."
                )

            if end_date is None and window_size is None:
                raise OperationalException(
                    "A window size is required or a start and end date "
                    "to retrieve ohlcv data."
                )

            if end_date is None:
                end_date = datetime.now(tz=timezone.utc)

            if start_date is None:

                if date is not None:
                    start_date = date
                else:
                    start_date = self.create_start_date(
                        end_date=end_date,
                        time_frame=time_frame,
                        window_size=window_size
                    )

            data = self.get_ohlcv(
                symbol=symbol,
                time_frame=time_frame,
                from_timestamp=start_date,
                market=market,
                to_timestamp=end_date
            )

            if pandas:
                data = convert_polars_to_pandas(data)

            return data

        raise OperationalException(
            f"Data type {data_type} is not supported for CCXTDataProvider"
        )

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


class CCXTOHLCVDataProvider(DataProvider):
    """
    CCXT OHLCV Data Provider is a data provider that uses the
    CCXT library to retrieve OHLCV data from various cryptocurrency
    markets. It supports multiple markets and symbols,
    """
    backtest_data_directory = None
    backtest_data_end_date = None
    total_minutes_time_frame = None
    column_names = ["Datetime", "Open", "High", "Low", "Close", "Volume"]

    def __init__(
        self,
        market=None,
        symbol=None,
        time_frame=None,
        window_size=None,
        priority=1
    ):
        super().__init__(
            data_type=TradingDataType.OHLCV.value,
            symbol=symbol,
            time_frame=time_frame,
            window_size=window_size,
            priority=priority
        )

        self.market = market
        self.data = None
        self._start_date_data_source = None
        self._end_date_data_source = None
        self.backtest_end_index = self.window_size
        self.backtest_start_index = 0
        self.window_cache = {}

    def pre_pare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        window_size=None
    ) -> None:
        pass

    def get_backtest_data(
        self,
        date: datetime = None,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        backtest_start_date: datetime = None,
        backtest_end_date: datetime = None,
        window_size=None,
        pandas=False
    ) -> None:
        pass

    def has_data(
        self,
        data_type: str = None,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        window_size=None,
    ) -> bool:

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

        except Exception:
            return False

    def get_data(
        self,
        data_type: str = None,
        date: datetime = None,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        storage_path=None,
        window_size=None,
        pandas=False,
        save: bool = True
    ) -> Union[pl.DataFrame, pd.DataFrame]:
        """
        Function to retrieve data from the CCXT data provider.
        This function retrieves OHLCV data for a given symbol, time frame,
        and market. It uses the CCXT library to fetch the data and returns
        it in a polars DataFrame format. If pandas is set to True, it
        converts the polars DataFrame to a pandas DataFrame.

        Args:
            data_type (str): The type of data to retrieve.
            date (datetime): The date to retrieve data for.
            symbol (str): The symbol to retrieve data for.
            market (str): The market to retrieve data from.
            time_frame (str): The time frame to retrieve data for.
            start_date (datetime): The start date to retrieve data from.
            end_date (datetime): The end date to retrieve data to.
            storage_path (str): The path to store the data.
            window_size (int): The size of the data window.
            pandas (bool): Whether to return the data as a pandas DataFrame.
            save (bool): Whether to save the data to the storage path.

        Returns:
            Union[pl.DataFrame, pd.DataFrame]: The retrieved data in
                Polars DataFrame format, or converted to pandas DataFrame
        """
        if market is None:
            market = self.market

        if market is None:
            raise OperationalException(
                "Market is not set. Please set the market "
                "before calling get_data."
            )

        if symbol is None:
            symbol = self.symbol

        if symbol is None:
            raise OperationalException(
                "Symbol is not set. Please set the symbol "
                "before calling get_data."
            )

        if data_type is None:
            data_type = self.data_type

        if TradingDataType.OHLCV.equals(data_type):

            if time_frame is None:
                time_frame = self.time_frame

            if time_frame is None:
                raise OperationalException(
                    "Time frame is not set. Please set the time frame "
                    "before requesting ohlcv data."
                )

            if end_date is None and window_size is None:
                raise OperationalException(
                    "A window size is required or a start and end date "
                    "to retrieve ohlcv data."
                )

            if end_date is None:
                end_date = datetime.now(tz=timezone.utc)

            if start_date is None:

                if date is not None:
                    start_date = date
                else:
                    start_date = self.create_start_date(
                        end_date=end_date,
                        time_frame=time_frame,
                        window_size=window_size
                    )

            # Check if the data already exists in the storage
            if storage_path is not None:
                # Here you would implement the logic to check if the data
                # exists in the storage path and return it if it does.
                # This is a placeholder for that logic.
                data = self.retrieve_data_from_storage(
                    storage_path=storage_path,
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
            else:
                data = self.get_ohlcv(
                    symbol=symbol,
                    time_frame=time_frame,
                    from_timestamp=start_date,
                    market=market,
                    to_timestamp=end_date
                )

            if save:
                # Here you would implement the logic to save the data
                # to the specified storage path.
                # This is a placeholder for that logic.
                self.save_data_to_storage(
                    symbol=symbol,
                    market=market,
                    start_date=start_date,
                    end_date=end_date,
                    time_frame=time_frame,
                    data=data,
                    storage_path=storage_path
                )

            if pandas:
                data = convert_polars_to_pandas(data)

            return data

        raise OperationalException(
            f"Data type {data_type} is not supported for CCXTDataProvider"
        )

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

    def supports(self, market, symbol):
        """
        Function to check if the data provider supports
        the given market and symbol.

        Args:
            market (str): The market to check
            symbol (str): The symbol to check

        Returns:
            bool: True if the data provider supports the market and symbol,
                False otherwise
        """
        try:
            exchange_class = getattr(ccxt, market.lower())
            exchange = exchange_class()
            symbols = exchange.load_markets()
            return symbol.upper() in symbols
        except Exception as e:
            logger.error(
                f"Error checking support for {market} and {symbol}: {e}"
            )
            return False

    @staticmethod
    def initialize_exchange(market, market_credential):
        """
        Function to initialize the exchange for the market.

        Args:
            market (str): The market to initialize the exchange for
            market_credential (MarketCredential): The market credential to use
                for the exchange

        Returns:

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

    def retrieve_data_from_storage(
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
                data = pl.read_csv(file_path, has_header=True)
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

    def __repr__(self):
        return (
            f"CCXTOHLCVDataProvider(market={self.market}, "
            f"symbol={self.symbol}, time_frame={self.time_frame}, "
            f"window_size={self.window_size})"
        )

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
