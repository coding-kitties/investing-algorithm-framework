from abc import abstractmethod, ABC
from datetime import datetime


class BacktestMarketDataSource(ABC):

    def __init__(self, identifier=None, market=None, symbol=None, start_date=None, end_date=None):
        self._identifier = identifier
        self._market = market
        self._symbol = symbol
        self._start_date = start_date
        self._end_date = end_date

    @abstractmethod
    def prepare_data(self, config, backtest_start_date, backtest_end_date):
        pass

    @abstractmethod
    def get_data(self, backtest_index_date, **kwargs):
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


class MarketDataSource(ABC):

    def __init__(
        self,
        identifier,
        market,
        symbol
    ):
        self._identifier = identifier
        self._market = market
        self._symbol = symbol

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
        pass

    @abstractmethod
    def to_backtest_market_data_source(self) -> BacktestMarketDataSource:
        pass


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
