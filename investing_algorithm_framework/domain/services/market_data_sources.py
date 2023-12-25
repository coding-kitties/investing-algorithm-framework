from abc import abstractmethod, ABC
from typing import Callable
from datetime import datetime


class BacktestMarketDataSource(ABC):

    def __init__(
            self,
            identifier,
            market,
            symbol,
            start_date=None,
            end_date=None,
    ):
        self._identifier = identifier
        self._market = market
        self._symbol = symbol
        self._start_date = start_date
        self._end_date = end_date

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

    def __init__(
            self,
            identifier,
            market,
            symbol,
            timeframe,
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
        self._timeframe = timeframe
        self._start_date = start_date
        self._start_date_func = start_date_func
        self._end_date = end_date
        self._end_date_func = end_date_func

    @property
    def timeframe(self):
        return self._timeframe

    def get_timeframe(self):
        return self.timeframe

    @property
    def start_date(self):
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
