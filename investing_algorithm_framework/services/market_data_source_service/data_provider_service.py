import logging
from collections import defaultdict
from datetime import datetime
from typing import List

from investing_algorithm_framework.domain import DataProvider, \
    OperationalException, ImproperlyConfigured, DataSource

logger = logging.getLogger("investing_algorithm_framework")


class DataProviderIndex:
    """
    Efficient lookup for data providers in O(1) time.

    Attributes:
        data_providers (List[DataProvider]): List of data providers
        data_providers_lookup (dict): Dictionary to store the lookup
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

    def register(self, data_source: DataSource) -> DataProvider:
        """
        Register an ohlcv data provider for a given market and symbol.

        This method will also check if the data provider supports
        the market. If no data provider is found for the market and symbol,
        it will raise an ImproperlyConfigured exception.

        If multiple data providers are found for the market and symbol,
        it will sort them by priority and pick the best one.

        Args:
            data_source (DataSource): The data source to register the
                ohlcv data provider for.

        Returns:
            None
        """
        matches = []

        for data_provider in self.data_providers:

            if data_provider.has_data(data_source):
                matches.append(data_provider)

        if len(matches) == 0:
            dict = data_source.to_dict()
            raise ImproperlyConfigured(
                f"No data provider found for given parameters: {dict}."
                f" Please make sure that you have registered a data provider "
                f"provider for the market and symbol you are trying to use"
            )

        # Sort by priority and pick the best one
        best_provider = sorted(matches, key=lambda x: x.priority)[0]
        index_key = data_source.create_index_key()
        self.data_providers_lookup[index_key] = best_provider
        return best_provider

    def get(self, data_source: DataSource):
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
        index_key = data_source.create_index_key()
        return self.data_providers_lookup.get(index_key, None)

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

    def __len__(self):
        """
        Returns the number of data providers in the index.

        Returns:
            int: The number of data providers.
        """
        return len(self.data_providers_lookup)


class DataProviderService:
    data_provider_index: DataProviderIndex = None

    def __init__(
        self,
        configuration_service,
        market_credential_service,
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
        self.market_credential_service = market_credential_service

    def get_data(
        self,
        data_source: DataSource,
        date: datetime = None,
        start_date: datetime = None,
        end_date: datetime = None,
    ):
        """
        Function to get data from the data provider.

        Args:
            data_source (DataSource): The data source specification that
                matches a data provider.
            date (datetime): The date to get data for.
            start_date (datetime): The start date for the data.
            end_date (datetime): The end date for the data.

        Returns:
            DataFrame: The data for the given symbol and market.
        """

        data_provider = self.find_data_provider(
            data_source=data_source,
        )

        if data_provider is None:
            dict_data = data_source.to_dict()
            self._throw_no_data_provider_exception(dict_data)

        if self.configuration_service is not None:
            data_provider.config = self.configuration_service.get_config()

        return {}
        # return data_provider.get_data(
        #     data_source=data_source,
        #     start_date=start_date,
        #     end_date=end_date,
        #     storage_path=storage_path,
        #     window_size=window_size,
        #     pandas=pandas,
        #     save=save
        # )

    def get_backtest_data(
        self,
        data_source: DataSource,
        backtest_index_date: datetime,
        start_date: datetime = None,
        end_date: datetime = None,
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
            data_source
        )

        if data_provider is None:
            self._throw_no_data_provider_exception(data_source.to_dict())

        return data_provider.get_backtest_data(
            data_source=data_source,
            backtest_index_date=backtest_index_date,
            start_date=start_date,
            end_date=end_date,
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

        Returns:
            None
        """
        data_provider.priority = priority
        self.data_provider_index.add(data_provider)

    def find_data_provider(self, data_source):
        """
        Function to find a data provider based on the given parameters.

        Args:
            data_source (DataSource): The data source specification that
                matches a data provider.

        Returns:
            DataProvider: The data provider that matches the given parameters.
        """
        return self.data_provider_index.get(data_source)

    def index_data_providers(self, data_sources: List[DataSource]):
        """
        Index the data providers in the service.
        This will create a fast lookup index for the data providers
        based on the given parameters.

        Args:
            data_sources (List[DataSource]): The data sources to index.

        Returns:
            None
        """

        for data_source in data_sources:
            self.data_provider_index.register(data_source)
            logger.debug(f"Registered data source: {data_source}")
