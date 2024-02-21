import logging
import os
import csv
from abc import abstractmethod, ABC
from datetime import datetime, timedelta
from typing import Callable

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
        start_date=None,
        end_date=None,
        backtest_data_start_date=None,
        backtest_data_index_date=None,
    ):
        self._identifier = identifier
        self._market = market
        self._symbol = symbol
        self._start_date = start_date
        self._end_date = end_date
        self._backtest_data_start_date = backtest_data_start_date
        self._backtest_data_index_date = backtest_data_index_date

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
        except Exception as e:
            logger.error(f"Error reading {file_path}")
            logger.error(e)
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
    def get_data(
        self,
        backtest_index_date,
        from_time_stamp=None,
        to_time_stamp=None,
        **kwargs
    ):
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
    def get_data(
        self,
        time_stamp=None,
        from_time_stamp=None,
        to_time_stamp=None,
        **kwargs
    ):
        """
        Get data from the market data source.

        :param time_stamp: The time stamp of the data to get.
        :param from_time_stamp: The time stamp from which to get data.
        :param to_time_stamp: The time stamp to which to get data.
        :param kwargs: Additional arguments.
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
        start_date=None,
        start_date_func=None,
        end_date=None,
        end_date_func=None,
    ):
        super().__init__(
            identifier=identifier,
            market=market,
            symbol=symbol,
        )
        self._window_size = window_size
        self._timeframe = timeframe
        self._start_date = start_date
        self._start_date_func = start_date_func
        self._end_date = end_date
        self._end_date_func = end_date_func
        self.initialize_window_size()

    def initialize_window_size(self):
        """
        Method to determine the window size of ohlcv market data source
        """
        if self._window_size is None:
            start_date = self.start_date
            end_date = self.end_date

            if not isinstance(start_date, datetime):
                raise OperationalException(
                    "start_date or start_date_func must be a datetime object"
                )

            if not isinstance(end_date, datetime):
                raise OperationalException(
                    "end_date or end_date_func must be a datetime object"
                )

            minutes_diff = \
                (self.end_date - self.start_date).total_seconds() / 60
            windows_size_minutes = TimeFrame.from_string(self.timeframe)\
                .amount_of_minutes

            self._window_size = minutes_diff / windows_size_minutes

    @property
    def timeframe(self):
        return self._timeframe

    def get_timeframe(self):
        return self.timeframe

    @property
    def start_date(self):
        """
        Get the start date of the market data source.

        if window_size is not None and the start date is,
        the start date will be calculated based on the end date
        and the window size.

        If the start date is not None, the start date will be returned.

        If the start date function is not None, the start date function will
        be called and the result will be returned.
        """

        if self.window_size is not None:

            if self._start_date is not None:
                return self._start_date

            minutes = TimeFrame.from_string(self.timeframe).amount_of_minutes
            return self.end_date - \
                timedelta(minutes=self.window_size * minutes)

        if self._start_date_func is not None:
            return self._start_date_func()
        else:
            return self._start_date

    def get_start_date(self):
        return self.start_date

    @property
    def start_date_func(self):
        return self._start_date_func

    @property
    def end_date(self):

        if self._end_date_func is not None:
            return self._end_date_func()
        elif self._end_date is not None:
            return self._end_date
        else:
            return datetime.utcnow()

    def get_end_date(self):
        return self.end_date

    @property
    def end_date_func(self):
        return self._end_date_func

    @end_date.setter
    def end_date(self, value):
        self._end_date = value

    @start_date.setter
    def start_date(self, value):
        self._start_date = value

    @end_date_func.setter
    def end_date_func(self, func: Callable):
        self._end_date_func = func

    @start_date_func.setter
    def start_date_func(self, func: Callable):
        self._start_date_func = func

    @property
    def window_size(self):
        return self._window_size


class TickerMarketDataSource(MarketDataSource, ABC):

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
