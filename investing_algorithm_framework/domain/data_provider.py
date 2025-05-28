from typing import List
from abc import ABC, abstractmethod
from datetime import datetime
from investing_algorithm_framework.domain import TradingDataType, TimeFrame


class DataProvider(ABC):
    """
    Abstract base class for data providers. The DataProvider class
    is responsible for fetching and preparing data for trading
    algorithms.

    Attributes:
        data_type (str): The type of data to be
            fetched (e.g., OHLCV, TICKER, CUSTOM_DATA).
        symbols (Optional[List[str]]): A list supported symbols that the
            data provider can provide data for. The framework will use this
            list when searching for a data provider for a specific symbol.
            Example: ["AAPL/USD", "GOOGL/USD", "MSFT/USD"]
        markets (Optional[List[str]]): A list supported markets that the
            data provider can provide data for. The framework will use this
            list when searching for a data provider for a specific market.
            Example: ["BINANCE", "COINBASE", "KRAKEN"]
        priority (int): The priority of the data provider. The lower the
            number, the higher the priority. The framework will use this
            priority when searching for a data provider for a specific symbol.
            Example: 0 is the highest priority, 1 is the second highest
            priority, etc. This is useful when multiple data providers
            support the same symbol or market. The framework will use the
            data provider with the highest priority.
        time_frame (Optional[str]): The time frame for the data. This is
            useful for data providers that support multiple time frames.
            Example: "1m", "5m", "1h", "1d"
        window_size (Optional[int]): The window size for the data. This is
            useful for data providers that support multiple window sizes.
            Example: 100, 200, 500
        storage_path (Optional[str]): The path to the storage location
            for the data. This is useful for data providers that support
            saving data to a file
    """

    def __init__(
        self,
        data_type: str,
        symbol: str = None,
        market: str = None,
        markets: list = None,
        priority: int = 0,
        time_frame=None,
        window_size=None,
        storage_path=None,
    ):
        """
        Initializes the DataProvider with data type, symbols, and markets.
        """
        self._data_type = None
        self._time_frame = None

        if data_type is not None:
            self._data_type = TradingDataType.from_value(data_type)

        if time_frame is not None:
            self.time_frame = TimeFrame.from_value(time_frame)

        self.symbol = symbol
        self.market = market
        self.markets = markets
        self.priority = priority
        self.window_size = window_size
        self.storage_path = storage_path
        self._market_credentials = None

    @property
    def data_type(self):
        return self._data_type

    @data_type.setter
    def data_type(self, value):
        self._data_type = TradingDataType.from_value(value)

    @property
    def time_frame(self):
        return self._time_frame

    @time_frame.setter
    def time_frame(self, value):
        self._time_frame = TimeFrame.from_value(value)

    @property
    def market_credentials(self):
        """
        Returns the market credentials for the data provider.
        """
        return self._market_credentials

    @market_credentials.setter
    def market_credentials(self, value: List):
        """
        Sets the market credentials for the data provider.
        """
        self._market_credentials = value

    def get_credential(self, market: str):
        """
        Returns the credentials for the given market.
        """
        if self.market_credentials is None:
            return None
        for credential in self.market_credentials:
            if credential.market == market:
                return credential
        return None

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, value):
        self._config = value

    @abstractmethod
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
        """
        Checks if the data provider has data for the given parameters.
        """
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
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
        save: bool = True,
    ):
        """
        Fetches data for a given symbol and date range.
        """
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    def pre_pare_backtest_data(
        self,
        backtest_start_date,
        backtest_end_date,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        window_size=None,
    ) -> None:
        """
        Prepares backtest data for a given symbol and date range.
        """
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    def get_backtest_data(
        self,
        date: datetime = None,
        symbol: str = None,
        market: str = None,
        time_frame: str = None,
        backtest_start_date: datetime = None,
        backtest_end_date: datetime = None,
        window_size=None,
        pandas=False,
    ) -> None:
        """
        Fetches backtest data for a given symbol and date range.
        """
        raise NotImplementedError("Subclasses should implement this method.")
