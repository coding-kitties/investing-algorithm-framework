import logging
from collections import defaultdict
from datetime import datetime
from typing import List, Optional

from investing_algorithm_framework.domain import DataProvider, \
    OperationalException, ImproperlyConfigured, TradingDataType

logger = logging.getLogger("investing_algorithm_framework")


class DataProviderIndex:
    """
    Class to index data providers. Given a list of data providers, each data
    provider will be indexed given that it has support for the given query
    params
    """

    def __init__(self, data_providers: List[DataProvider] = []):
        self.data_providers: List[DataProvider] = data_providers

    def register_data_provider(self, data_provider: DataProvider) -> None:
        """
        Register a new data provider.

        Args:
            data_provider (DataProvider): The data provider to register.
        """
        self.data_providers.append(data_provider)


class OHLCVDataProviderIndex:
    """
    Efficient lookup for ohlcv data providers in O(1) time.

    Attributes:
        data_providers (List[DataProvider]): List of data providers
        order_executor_lookup (dict): Dictionary to store the lookup
            for order executors based on market.
    """
    def __init__(self, data_providers=[]):
        self.data_providers = data_providers
        self.data_providers_lookup = defaultdict()

    def add(self, data_provider: DataProvider):
        """
        Add a data provider to the lookup.

        Args:
            data_provider (DataProvider): The data provider to be added.

        Returns:
            None
        """
        self.data_providers.append(data_provider)

    def register(self, symbol, market) -> DataProvider:
        """
        Register an ohlcv data provider for a given market and symbol.

        This method will also check if the data provider supports
        the market. If no data provider is found for the market and symbol,
        it will raise an ImproperlyConfigured exception.

        If multiple data providers are found for the market and symbol,
        it will sort them by priority and pick the best one.

        Args:
            market (str): The market to register the data provider for.
            symbol (str): The symbol to register the data provider for.

        Returns:
            None
        """
        matches = []

        for data_provider in self.data_providers:

            if data_provider.supports(market, symbol):
                matches.append(data_provider)

        if len(matches) == 0:
            raise ImproperlyConfigured(
                f"No data provider found for market "
                f"{market} and symbol {symbol}."
                f" Please make sure that you have registered a data provider "
                f"provider for the market and symbol you are trying to use"
            )

        # Sort by priority and pick the best one
        best_provider = sorted(matches, key=lambda x: x.priority)[0]
        self.data_providers_lookup[(market, symbol)] = best_provider
        return best_provider

    def get(self, symbol, market: str):
        """
        Get the ohlcv data provider for a given market and symbol.
        If no data provider is found for the market and symbol,
        it will return None.

        Args:
            market (str): The market to get the order executor for.
            symbol (str): The symbol to get the order executor for.

        Returns:
            DataProvider: The data provider for the market and symbol,
        """
        return self.data_providers_lookup.get((market, symbol), None)

    def get_all(self) -> List[DataProvider]:
        """
        Get all order executors.
        This method will return all order executors that are currently
        registered in the order_executors list.

        Returns:
            List[OrderExecutor]: A list of all order executors.
        """
        return self.data_providers

    def reset(self):
        """
        Function to reset the order executor lookup table

        Returns:
            None
        """
        self.data_providers_lookup = defaultdict()
        self.data_providers = []


class DataProviderService:
    data_providers: List[DataProvider] = []
    default_data_providers: List[DataProvider] = [
        # Add default data providers here
    ]
    data_provider_index: DataProviderIndex = None
    ohlcv_data_provider_index: OHLCVDataProviderIndex = None

    def __init__(
        self,
        configuration_service,
        market_credentials_service,
        default_data_providers: List[DataProvider] = [],
        default_ohlcv_data_providers: List[DataProvider] = []
    ):
        """
        Initialize the DataProviderService with a list of data providers.

        Args:
            default_data_providers (List[DataProvider]): A list of default
                data providers to use.
        """
        self.default_data_providers = default_data_providers
        self.data_provider_index = DataProviderIndex(default_data_providers)
        self.configuration_service = configuration_service
        self.market_credentials_service = market_credentials_service
        self.ohlcv_data_provider_index = OHLCVDataProviderIndex(
            data_providers=default_ohlcv_data_providers
        )

    def get_data(
        self,
        symbol: str,
        data_type=None,
        date: datetime = None,
        market: str = None,
        time_frame: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        storage_path=None,
        window_size=None,
        pandas=False,
        save: bool = False,
    ):
        """
        Function to get data from the data provider.

        Args:
            data_type (str): The type of data to get (e.g., "ohlcv", "ticker").
            date (datetime): The date to get data for.
            symbol (str): The symbol to get data for.
            market (str): The market to get data from.
            time_frame (str): The time frame to get data for.
            start_date (datetime): The start date for the data.
            end_date (datetime): The end date for the data.
            storage_path (str): The path to store the data.
            window_size (int): The size of the data window.
            pandas (bool): Whether to return the data as a pandas DataFrame.

        Returns:
            DataFrame: The data for the given symbol and market.
        """

        data_provider = self.find_data_provider(
            symbol=symbol, market=market, data_type=data_type
        )

        if data_provider is None:
            self._throw_no_data_provider_exception(
                {
                    "symbol": symbol,
                    "market": market,
                    "data_type": data_type,
                    "time_frame": time_frame,
                }
            )

        if self.configuration_service is not None:
            data_provider.config = self.configuration_service.get_config()

        return data_provider.get_data(
            data_type=data_type,
            date=date,
            symbol=symbol,
            market=market,
            time_frame=time_frame,
            start_date=start_date,
            end_date=end_date,
            storage_path=storage_path,
            window_size=window_size,
            pandas=pandas,
            save=save
        )

    def get_backtest_data(
        self,
        symbol: str,
        data_type: str,
        market: str = None,
        backtest_index_date: datetime = None,
        time_frame: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        storage_path=None,
        window_size=None,
        pandas=False,
        save: bool = False,
    ):

        """
        Function to get backtest data from the data provider.

        Args:
            symbol (str): The symbol to get data for.
            market (str): The market to get data from.
            time_frame (str): The time frame to get data for.
            start_date (datetime): The start date for the data.
            end_date (datetime): The end date for the data.
            storage_path (str): The path to store the data.
            window_size (int): The size of the data window.
            pandas (bool): Whether to return the data as a pandas DataFrame.

        Returns:
            DataFrame: The backtest data for the given symbol and market.
        """
        data_provider = self.data_provider_index.find_data_provider(
            symbol=symbol,
            market=market,
            time_frame=time_frame,
        )

        if data_provider is None:
            self._throw_no_data_provider_exception(
                {
                    "symbol": symbol,
                    "market": market,
                    "data_type": data_type,
                    "time_frame": time_frame,
                }
            )

        return data_provider.get_backtest_data(
            symbol=symbol,
            market=market,
            time_frame=time_frame,
            backtest_index_date=backtest_index_date,
            start_date=start_date,
            end_date=end_date,
            storage_path=storage_path,
            window_size=window_size,
            pandas=pandas,
        )

    def _throw_no_data_provider_exception(self, params):
        """
        Raise an exception if no data provider is found for the given params
        """
        non_null_params = {k: v for k, v in params.items() if v is not None}
        if len(non_null_params) == 0:
            raise OperationalException(
                "No data provider found for the given parameters"
            )

        params = ", ".join(
            [f"{k}: {v}" for k, v in non_null_params.items()]
        )

        raise OperationalException(
            f"No data provider found for the given parameters: {params}"
        )

    def add_data_provider(
        self, data_provider: DataProvider, priority: int = 0
    ):
        """
        Add a data provider to the service.

        Args:
            data_provider (DataProvider): The data provider to add.
            priority (int): The priority of the data provider.
        """
        self.data_providers.append(data_provider)
        self.data_providers.sort(key=lambda x: x.priority, reverse=True)

    def find_data_provider(
        self,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
        data_type: Optional[str] = None,
        time_frame: Optional[str] = None,
    ):
        """
        Function to find a data provider based on the given parameters.

        Args:
            symbol (str): The symbol to find the data provider for.
            market (str): The market to find the data provider for.
            data_type (str): The type of data to find the data provider for.
            time_frame (str): The time frame to find the data provider for.

        Returns:
            DataProvider: The data provider that matches the given parameters.
        """
        data_provider = None

        if TradingDataType.OHLCV.equals(data_type):
            # Check if there is already a registered data provider
            data_provider = self.ohlcv_data_provider_index.get(
                symbol=symbol, market=market
            )

            if data_provider is None:
                # Try to register a new data provider if it is not
                # already registered
                data_provider = self.ohlcv_data_provider_index.register(
                    symbol=symbol, market=market
                )

        return data_provider
