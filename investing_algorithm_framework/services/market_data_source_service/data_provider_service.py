import logging
from datetime import datetime
from typing import List, Optional

from investing_algorithm_framework.domain import DataProvider, \
    OperationalException, NetworkError

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

    def find_data_provider(
        self,
        symbol: Optional[str] = None,
        market: Optional[str] = None,
        data_type: Optional[str] = None,
        time_frame: Optional[str] = None,
    ):
        number_of_network_errors = 0
        matching_providers = []

        try:
            for provider in self.data_providers:
                if provider.has_data(
                    symbol=symbol,
                    market=market,
                    data_type=data_type,
                    time_frame=time_frame,
                ):
                    matching_providers.append(provider)
        except NetworkError as e:
            number_of_network_errors += 1
        except Exception as e:
            pass

        if len(matching_providers) == 0 and number_of_network_errors > 0:
            raise NetworkError(
                "Network error occurred, make sure you have "
                "an active internet connection"
            )

        # Sort by priority (lower priority number is better)
        matching_providers.sort(key=lambda p: p.priority)
        return matching_providers[0] if matching_providers else None

class DataProviderService:
    data_providers: List[DataProvider] = []
    default_data_providers: List[DataProvider] = [
        # Add default data providers here
    ]
    data_provider_index: DataProviderIndex = None

    def __init__(
        self,
        configuration_service,
        market_credentials_service,
        default_data_providers: List[DataProvider] = []
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

    def _initialize_data_providers(self):
        """
        Initialize all data providers.

        This function will call the load_markets and load_symbols
        methods of all data providers to load the markets and
        symbols for each data provider. It will also create a
        DataProviderIndex to index the data providers by symbol
        and market.
        """
        pass

        # if len(self.data_providers) == 0:
        #     logger.info(
        #         "No custom data providers found, using default data providers"
        #     )

        # for provider in self.default_data_providers:
        #     provider.load_markets()
        #     provider.load_symbols()

        # Create all indexes
        # self.data_provider_index = DataProviderIndex(self.data_providers)

    def get_data(
        self,
        symbol: str,
        data_type = None,
        date: datetime = None,
        market: str = None,
        time_frame: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        storage_path = None,
        window_size = None,
        pandas = False,
        save: bool = False,
    ):
        """
        Function to get data from the data provider.

        Args:
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

        data_provider = self.data_provider_index.find_data_provider(
            symbol=symbol
        )
        data_provider.config = self.configuration_service.get_config()

        if data_provider is None:
            self._throw_no_data_provider_exception(
                {
                    "symbol": symbol,
                    "market": market,
                    "data_type": data_type,
                    "time_frame": time_frame,
                }
            )

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

    def add_data_provider(self, data_provider: DataProvider, priority: int = 0):
        """
        Add a data provider to the service.

        Args:
            data_provider (DataProvider): The data provider to add.
            priority (int): The priority of the data provider.
        """
        self.data_providers.append(data_provider)
        self.data_providers.sort(key=lambda x: x.priority, reverse=True)