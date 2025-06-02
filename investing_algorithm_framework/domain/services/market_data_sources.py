import csv
import logging
import os
from abc import abstractmethod, ABC
from datetime import datetime, timedelta

import polars

from investing_algorithm_framework.domain import TimeFrame, \
    OperationalException

logger = logging.getLogger(__name__)


class BacktestMarketDataSource(ABC):
    column_names = []

    def __init__(
        self,
        identifier,
        market,
        symbol,
        backtest_data_start_date=None,
        backtest_data_index_date=None,
    ):
        self._identifier = identifier
        self._market = market
        self._symbol = symbol
        self._backtest_data_start_date = backtest_data_start_date
        self._backtest_data_index_date = backtest_data_index_date

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, value):
        self._config = value

    def _data_source_exists(self, file_path):
        """
        Function to check if the data source exists.
        This function will check if the file exists and if the column names
        are correct.

        This function will return True if the file exists and the column names
        are correct. If the file does not exist or the column names are not
        correct, this function will return False.

        This function prevents the backtest datasource to download the data
        every time the backtest is run.

        Args:
            file_path: str - the file path of the data storage file

        Returns:
            bool - True if the file exists and the column names are correct,
        """

        try:
            if os.path.isfile(file_path):
                df = polars.read_csv(file_path)

                if df.columns != self.column_names:
                    raise OperationalException(
                        f"Wrong column names on {file_path}, required "
                        f"column names are {self.column_names}"
                    )
            else:
                return False

            return True
        except Exception:
            return False

    def write_data_to_file_path(self, data_file, data):
        """
        Function to write data to a csv file.
        This function will write the column names and all the data to the
        file.
        """
        with open(data_file, "w") as file:
            column_headers = self.column_names
            writer = csv.writer(file)
            writer.writerow(column_headers)
            rows = data
            writer.writerows(rows)

    @abstractmethod
    def prepare_data(
        self,
        config,
        backtest_start_date,
        backtest_end_date,
    ):
        """
        Function to prepare the data for the backtest.
        This function needs to be implemented by the child class.

        Args:
            config: dict - the configuration of the application
            backtest_start_date: datetime - the start date of the backtest
            backtest_end_date: datetime - the end date of the backtest

        Returns:
            None
        """
        pass

    @abstractmethod
    def get_data(self, date, config):
        """
        Function to get the data for the backtest. This function needs to be
        implemented by the child class.

        Args:
            date: datetime - the date for which the data is required
            config: dict - the configuration of the application
        """
        pass

    @property
    def identifier(self):
        return self._identifier

    def get_identifier(self):
        return self.identifier

    @property
    def market(self):
        return self._market

    def get_market(self):
        return self.market

    @property
    def symbol(self):
        return self._symbol

    def get_symbol(self):
        return self.symbol

    @abstractmethod
    def empty(self):
        pass

    @property
    def market_credential_service(self):
        return self._market_credential_service

    @market_credential_service.setter
    def market_credential_service(self, value):
        self._market_credential_service = value

    @property
    def backtest_data_start_date(self):
        return self._backtest_data_start_date

    @backtest_data_start_date.setter
    def backtest_data_start_date(self, value):
        self._backtest_data_start_date = value

    @property
    def backtest_data_index_date(self):
        return self._backtest_data_index_date

    @backtest_data_index_date.setter
    def backtest_data_index_date(self, value):
        self._backtest_data_index_date = value


class MarketDataSource(ABC):

    def __init__(
        self,
        market,
        symbol,
        identifier=None,
        storage_path=None
    ):
        self._identifier = identifier
        self._market = market
        self._symbol = symbol
        self._market_credential_service = None
        self._config = None
        self._storage_path = storage_path

        if self._identifier is None:
            self._identifier = f"{self.market}_{self.symbol}"

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, value):
        self._config = value

    def initialize(self, config):
        pass

    @property
    def identifier(self):
        return self._identifier

    @identifier.setter
    def identifier(self, value):
        self._identifier = value

    def get_identifier(self):
        return self.identifier

    @property
    def market(self):
        return self._market

    def get_market(self):
        return self.market

    @property
    def symbol(self):
        return self._symbol

    def get_symbol(self):
        return self.symbol

    @property
    def storage_path(self):
        return self._storage_path

    def get_storage_path(self):
        return self.storage_path

    @abstractmethod
    def get_data(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        config=None,
    ):
        """
        Get data from the market data source.

        Args:
            config (dict): the configuration of the application
            start_date (optional) (datetime): the start date of the data
            end_date (optional) (datetime): the end date of the data

        Returns:
            DataFrame: the data from the market data source
        """
        pass

    @abstractmethod
    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        pass

    @property
    def market_credential_service(self):
        return self._market_credential_service

    @market_credential_service.setter
    def market_credential_service(self, value):
        self._market_credential_service = value

    @staticmethod
    def get_file_name_symbol(file_path):
        """
        Static function that extracts the symbol from a give data filepath,
        given that the data file path is in the format
        {DATA_TYPE}_{TARGET_SYMBOL}_{TRADING_SYMBOL}_{MARKET}_
        {time_frame}_{START_DATETIME}_{END_DATETIME}.csv

        Parameters:
            file_path: str - the given file path of
            the data storage file

        Returns:
            string representing the symbol
        """
        parts = file_path.split("_")

        if len(parts) < 6:
            return None

        return "".join([parts[1], '/', parts[2]])

    @staticmethod
    def get_file_name_time_frame(file_path):
        """
        Static function that extracts the time_frame from a give data filepath,
        given that the data file path is in the format
        {DATA_TYPE}_{TARGET_SYMBOL}_{TRADING_SYMBOL}_{MARKET}_
        {time_frame}_{START_DATETIME}_{END_DATETIME}.csv

        Parameters:
            file_path: str - the given file path of the data storage file

        Returns:
            string representing the time_frame
        """
        parts = file_path.split("_")

        if len(parts) < 6:
            return None

        return TimeFrame.from_string(parts[4])

    @staticmethod
    def get_file_name_market(file_path):
        """
        Static function that extracts the time_frame from a give data filepath,
        given that the data file path is in the format
        {DATA_TYPE}_{TARGET_SYMBOL}_{TRADING_SYMBOL}_{MARKET}
        _{time_frame}_{START_DATETIME}_{END_DATETIME}.csv

        Parameters:
            file_path: str - the given file path of the data storage file

        Returns:
            string representing the market
        """
        parts = file_path.split("_")

        if len(parts) < 6:
            return None

        return TimeFrame.from_string(parts[3])

    @staticmethod
    def get_file_name_start_datetime(file_path):
        """
        Static function that extracts the time_frame from a give data filepath,
        given that the data file path is in the format
        {DATA_TYPE}_{TARGET_SYMBOL}_{TRADING_SYMBOL}_{MARKET}_
        {time_frame}_{START_DATETIME}_{END_DATETIME}.csv

        Parameters:
            file_path: str - the given file path of the data storage file

        Returns:
            string representing the start datetime
        """
        parts = file_path.split("_")

        if len(parts) < 6:
            return None

        return TimeFrame.from_string(parts[5])

    @staticmethod
    def get_file_name_end_datetime(file_path):
        """
        Static function that extracts the time_frame
        from a give data filepath, given that the data file
        path is in the format
        {DATA_TYPE}_{TARGET_SYMBOL}_{TRADING_SYMBOL}_{MARKET}_
        {time_frame}_{START_DATETIME}_{END_DATETIME}.csv

        Parameters:
            file_path: str - the given file path of the data storage file

        Returns:
            string representing the end datetime
        """
        parts = file_path.split("_")

        if len(parts) < 6:
            return None

        return TimeFrame.from_string(parts[6])

    @staticmethod
    def create_storage_file_path(
        storage_path,
        data_type,
        symbol,
        market,
        time_frame,
        start_datetime,
        end_datetime,
    ):
        """
        Static function that creates a storage file path given the parameters

        Parameters:
            storage_path: str - the storage path of the data storage file
            data_type: str - the type of data
            symbol: str - the asset symbol
            market: str - the market
            time_frame: str - the time_frame
            start_datetime: datetime - the start datetime
            end_datetime: datetime - the end datetime

        Returns:
            string representing the storage file path
        """

        target_symbol, trading_symbol = symbol.split('/')
        path = os.path.join(
            storage_path,
            f"{data_type}_{target_symbol}_{trading_symbol}_{market}_" +
            f"{time_frame}_{start_datetime}_{end_datetime}.csv"
        )
        return path


class OHLCVMarketDataSource(MarketDataSource, ABC):
    """
    Abstract class for ohlcv market data sources.
    """
    def __init__(
        self,
        market,
        symbol,
        time_frame,
        identifier=None,
        window_size=None,
        storage_path=None,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
            storage_path=storage_path
        )
        self._window_size = window_size
        self._time_frame = time_frame

    @property
    def time_frame(self):
        return self._time_frame

    def get_time_frame(self):
        return self.time_frame

    def create_start_date(self, end_date, time_frame, window_size):
        minutes = TimeFrame.from_value(time_frame).amount_of_minutes
        return end_date - timedelta(minutes=window_size * minutes)

    def create_end_date(self, start_date, time_frame, window_size):
        minutes = TimeFrame.from_value(time_frame).amount_of_minutes
        return start_date + timedelta(minutes=window_size * minutes)

    @property
    def window_size(self):
        return self._window_size

    @window_size.setter
    def window_size(self, value):

        if not isinstance(value, int):
            raise OperationalException(
                "Window size must be an integer"
            )

        self._window_size = value

    def get_date_ranges(
        self,
        start_date: datetime,
        end_date: datetime,
        window_size: int,
        time_frame
    ):
        """
        Function to get the date ranges of the market data source based
        on the window size and the time_frame. The date ranges
        will be calculated based on the start date and the end date.

        Args:
            start_date: datetime - The start date
            end_date: datetime - The end date
            window_size: int - The window size
            time_frame: str - The time frame

        Returns:
            list - A list of tuples with the date ranges
        """

        if start_date > end_date:
            raise OperationalException(
                "Start date must be before end date"
            )

        time_frame = TimeFrame.from_value(time_frame)
        new_end_date = start_date + timedelta(
            minutes=window_size * time_frame.amount_of_minutes
        )
        ranges = [(start_date, new_end_date)]
        start_date = new_end_date

        if new_end_date > end_date:
            return [(start_date, end_date)]

        while start_date < end_date:
            new_end_date = start_date + timedelta(
                minutes=self.window_size * time_frame.amount_of_minutes
            )

            if new_end_date > end_date:
                new_end_date = end_date

            ranges.append((start_date, new_end_date))
            start_date = new_end_date

        return ranges


class TickerMarketDataSource(MarketDataSource, ABC):
    """
    Abstract class for ticker market data sources.
    """

    def __init__(
            self,
            identifier,
            market=None,
            symbol=None,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
        )


class OrderBookMarketDataSource(MarketDataSource, ABC):
    """
    Abstract class for order book market data sources.
    """

    def __init__(
            self,
            identifier,
            market,
            symbol,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
        )
