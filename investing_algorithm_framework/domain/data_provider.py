from typing import List, Any, Union
from abc import ABC, abstractmethod
from datetime import datetime
from investing_algorithm_framework.domain.exceptions import \
    ImproperlyConfigured
from investing_algorithm_framework.domain.models.time_frame import TimeFrame
from investing_algorithm_framework.domain.models.data.data_type import DataType
from investing_algorithm_framework.domain.models.data.data_source import \
    DataSource


class DataProvider(ABC):
    """
    Abstract base class for data providers. The DataProvider class
    is responsible for fetching and preparing data for trading
    algorithms.

    Attributes:
        data_type (DataType): The type of data to be
            fetched (e.g., OHLCV, TICKER, CUSTOM_DATA).
        symbol (Optional[List[str]]): A list supported symbols that the
            data provider can provide data for. The framework will use this
            list when searching for a data provider for a specific symbol.
            Example: ["AAPL/USD", "GOOGL/USD", "MSFT/USD"]
        priority (int): The priority of the data provider. The lower the
            number, the higher the priority. The framework will use this
            priority when searching for a data provider for a specific symbol.
            Example: 0 is the highest priority, 1 is the second-highest
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
    data_type: DataType = None
    data_provider_identifier: str = None

    def __init__(
        self,
        data_provider_identifier: str = None,
        data_type: str = None,
        symbol: str = None,
        market: str = None,
        priority: int = 0,
        time_frame=None,
        window_size=None,
        storage_path=None,
        storage_directory=None,
        config=None,
    ):
        """
        Initializes the DataProvider. The data provider should be defined
        with a data_type and a data_provider_identifier. The data_type
        should be a valid DataType, and the data_provider_identifier
        should be a unique identifier for the data provider.

        Args:
            data_provider_identifier (str): The unique identifier for the
                data provider. This is used to identify the data provider
                in the framework. It should be a unique string that identifies
                the data provider. Example: "binance",
                "coinbase", "custom_feed_data"
            data_type (str): The type of data to be fetched
                (e.g., "OHLCV", "TICKER", "CUSTOM_DATA")
            symbol (str): The symbol to fetch data for. This is optional and
                can be set later. Example: "AAPL/USD", "BTC/USD"
            market (str): The market to fetch data for.
                This is optional and can be set later.
                Example: "BINANCE", "COINBASE"
            priority (int): The priority of the data provider. The lower the
                number, the higher the priority. This is useful when multiple
                data providers support the same symbol or market. The framework
                will use the data provider with the highest priority.
                Example: 0 is the highest priority, 1 is the second-highest
                priority, etc.
            time_frame (str): The time frame for the data. This is optional and
                can be set later. This is useful for data providers
                that support multiple time frames.
                Example: "1m", "5m", "1h", "1d"
            window_size (int): The window size for the data. This is optional
                and can be set later. This is useful for data providers that
                support multiple window sizes. Example: 100, 200, 500
            storage_path (str): The path to the storage location for the data.
                This is optional and can be set later. This is useful for data
                providers that support saving data to a file.
                Example: "/path/to/data"
        """
        self._data_type = None
        self._time_frame = None

        if data_type is not None:
            self.data_type = DataType.from_value(data_type)

        if time_frame is not None:
            self.time_frame = TimeFrame.from_value(time_frame)

        if data_provider_identifier is not None:
            self.data_provider_identifier = data_provider_identifier

        self.symbol = symbol

        if self.symbol is not None:
            self.symbol = self.symbol.upper()

        self.market = market

        if self.market is not None:
            self.market = self.market.upper()

        self.priority = priority
        self._config = config
        self.window_size = window_size
        self.storage_path = storage_path
        self.storage_directory = storage_directory
        self._market_credentials = None

        # Check if the data provider is properly configured
        if self.data_type is None:
            raise ImproperlyConfigured(
                "DataProvider must be initialized "
                "with a data_type. Either pass it as a parameter in "
                "the constructor or set it as a class attribute."
            )

        if self.data_provider_identifier is None:
            raise ImproperlyConfigured(
                "DataProvider must be initialized with a "
                "data_provider_identifier. Either pass it as a parameter "
                "in the constructor or set it as a class attribute."
            )

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
        data_source: DataSource,
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> bool:
        """
        Checks if the data provider has data for the given parameters.

        Args:
            data_source (DataSource): The data source specification that
                matches a data provider.
            start_date (datetime): The start date for the data.
            end_date (datetime): The end date for the data.

        Returns:
            bool: True if the data provider has data for the given parameters,
        """
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    def get_data(
        self,
        date: datetime = None,
        start_date: datetime = None,
        end_date: datetime = None,
        save: bool = False,
    ) -> Any:
        """
        Fetches data for a given symbol and date range.

        Args:
            start_date (datetime): The start date for the data.
            end_date (datetime): The end date for the data.
            date (datetime): The specific date for which to fetch data.
            save (bool): Whether to save the data to the storage path.

        Returns:
            Any: The data for the given symbol and date range.
            This can be a DataFrame, a list, or any other data structure
            depending on the implementation.
        """
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
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

        Returns:
            None
        """
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    def get_backtest_data(
        self,
        backtest_index_date: datetime,
        backtest_start_date: datetime = None,
        backtest_end_date: datetime = None,
        data_source: DataSource = None,
    ) -> Any:
        """
        Fetches backtest data for a given datasource

        Args:
            backtest_index_date (datetime): The date for which to fetch
                backtest data.
            backtest_start_date (datetime): The start date for the
                backtest data.
            backtest_end_date (datetime): The end date for the
                backtest data.
            data_source (Optional[DataSource]): The data source
                specification that is used to fetch the data.
                This param is optional and can be used to
                help identify errors in data fetching.

        Returns:
            Any: The data for the given symbol and date range.
            This can be a DataFrame, a list, or any other data structure
            depending on the implementation.
        """
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    def copy(self, data_source: DataSource) -> "DataProvider":
        """
        Returns a copy of the data provider instance based on a
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
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    def get_number_of_data_points(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> int:
        """
        Returns the number of data points available between the
        given start and end dates.

        Args:
            start_date (datetime): The start date for the data points.
            end_date (datetime): The end date for the data points.
        Returns:
            int: The number of data points available between the
                given start and end dates.
        """
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
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
        raise NotImplementedError("Subclasses should implement this method.")

    @abstractmethod
    def get_data_source_file_path(self) -> Union[str, None]:
        """
        Returns the file path for the given data source if applicable.

        Returns:
            Union[str, None]: The file path for the data source or None
                if not applicable.
        """
        raise NotImplementedError("Subclasses should implement this method.")
