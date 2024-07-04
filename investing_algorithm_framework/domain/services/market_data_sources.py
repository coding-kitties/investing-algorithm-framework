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
        **kwargs
    ):
        pass

    @abstractmethod
    def get_data(self, **kwargs):
        """
        Get data from the market data source.
        :param kwargs: Additional arguments to get the data. Common arguments
        - start_date: datetime
        - end_date: datetime
        - timeframe: str
        - backtest_start_date: datetime
        - backtest_end_date: datetime
        - backtest_data_index_date: datetime
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
        identifier,
        market,
        symbol,
    ):
        self._identifier = identifier
        self._market = market
        self._symbol = symbol
        self._market_credential_service = None
        self._config = None

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
    def get_data(self, **kwargs):
        """
        Get data from the market data source.
        :param kwargs: Additional arguments to get the data. Common arguments
        - start_date: datetime
        - end_date: datetime
        - timeframe: str

        :return: Object with the data
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


class OHLCVMarketDataSource(MarketDataSource, ABC):
    """
    Abstract class for ohlcv market data sources.
    """
    def __init__(
        self,
        identifier,
        market,
        symbol,
        timeframe,
        window_size=None,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
        )
        self._window_size = window_size
        self._timeframe = timeframe

    @property
    def timeframe(self):
        return self._timeframe

    def get_timeframe(self):
        return self.timeframe

    def create_start_date(self, end_date, timeframe, window_size):
        minutes = TimeFrame.from_value(timeframe).amount_of_minutes
        return end_date - timedelta(minutes=window_size * minutes)

    def create_end_date(self, start_date, timeframe, window_size):
        minutes = TimeFrame.from_value(timeframe).amount_of_minutes
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
        timeframe
    ):
        """
        Function to get the date ranges of the market data source based
        on the window size and the timeframe. The date ranges
        will be calculated based on the start date and the end date.
        """

        if start_date > end_date:
            raise OperationalException(
                "Start date must be before end date"
            )

        timeframe = TimeFrame.from_value(timeframe)
        new_end_date = start_date + timedelta(
            minutes=window_size * timeframe.amount_of_minutes
        )
        ranges = [(start_date, new_end_date)]
        start_date = new_end_date

        if new_end_date > end_date:
            return [(start_date, end_date)]

        while start_date < end_date:
            new_end_date = start_date + timedelta(
                minutes=self.window_size * timeframe.amount_of_minutes
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
