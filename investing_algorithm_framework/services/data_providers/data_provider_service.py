import logging
import pandas as pd
import polars as pl
from collections import defaultdict
from datetime import datetime
from typing import List, Tuple, Optional, Dict, Any

from investing_algorithm_framework.domain import DataProvider, \
    OperationalException, ImproperlyConfigured, DataSource, DataType, \
    BacktestDateRange, tqdm, convert_polars_to_pandas, TimeFrame

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
        self.ohlcv_data_providers = defaultdict()
        self.ohlcv_data_providers_no_market = defaultdict()
        self.ohlcv_data_providers_with_timeframe = defaultdict()
        self.ticker_data_providers = defaultdict()

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
        Register a data source in the DataProvider Index.


        This method will go over all data providers and select the
        best matching data provider for the data source.

        If multiple data providers are found for the data source,
        it will sort them by priority and pick the best one.

        Args:
            data_source (DataSource): The data source to register the
                data provider for.

        Returns:
            None
        """
        matches = []

        for data_provider in self.data_providers:

            if data_provider.has_data(data_source):
                matches.append(data_provider)

        if len(matches) == 0:
            params = data_source.to_dict()
            raise ImproperlyConfigured(
                f"No data provider found for given parameters: {params}."
                f" Please make sure that you have registered a data provider "
                f"provider for the market and symbol you are trying to use"
            )
        # Sort by priority and pick the best one
        best_provider = sorted(matches, key=lambda x: x.priority)[0]
        best_provider = best_provider.copy(data_source)
        # Copy the data provider and set the attributes
        self.data_providers_lookup[data_source] = best_provider

        symbol = data_source.symbol
        market = data_source.market
        time_frame = data_source.time_frame

        if DataType.OHLCV.equals(data_source.data_type):
            if symbol not in self.ohlcv_data_providers:
                self.ohlcv_data_providers[(symbol, market)] = best_provider
                self.ohlcv_data_providers_no_market[symbol] = best_provider
                self.ohlcv_data_providers_with_timeframe[
                    (symbol, market, time_frame)
                ] = best_provider
            else:
                try:
                    # If the symbol already exists, we can update the provider
                    # has a more granular timeframe
                    existing_provider = self.ohlcv_data_providers[
                        (symbol, market)
                    ]

                    if existing_provider.time_frame > best_provider.time_frame:
                        self.ohlcv_data_providers[(symbol, market)] =\
                            best_provider

                    existing_provider = self.ohlcv_data_providers_no_market[
                        symbol
                    ]

                    if existing_provider.time_frame > best_provider.time_frame:
                        self.ohlcv_data_providers_no_market[symbol] =\
                            best_provider

                    time_frame_key = (symbol, market, time_frame)
                    self.ohlcv_data_providers_with_timeframe[
                        time_frame_key
                    ] = best_provider

                except Exception:
                    # If the existing provider does not have a time_frame
                    # attribute, we can safely ignore this
                    pass

        elif DataType.TICKER.equals(data_source.data_type):
            if symbol not in self.ticker_data_providers:
                self.ticker_data_providers[symbol] = best_provider

        return best_provider

    def register_backtest_data_source(
        self,
        data_source: DataSource,
        backtest_date_range: BacktestDateRange
    ) -> DataProvider:
        """
        Register a backtest data source for a given market and symbol.

        This method will also check if the data provider supports
        the market. If no data provider is found for the market and symbol,
        it will raise an ImproperlyConfigured exception.

        Args:
            data_source (DataSource): The data source to register the
                backtest data provider for.
            backtest_date_range (BacktestDateRange): The date range for the
                backtest data provider.

        Returns:
            DataProvider: The registered data provider.
        """
        matches = []

        for data_provider in self.data_providers:

            if data_provider.has_data(
                data_source,
                start_date=backtest_date_range.start_date,
                end_date=backtest_date_range.end_date
            ):
                matches.append(data_provider)

        if len(matches) == 0:
            params = data_source.to_dict()
            raise ImproperlyConfigured(
                f"No data provider found for given parameters: {params}."
                f" Please make sure that you have registered a data provider "
                f"provider for the defined datasource. If you are using a "
                "custom data provider, make sure it has a "
                "data_provider_identifier set"
            )

        # Sort by priority and pick the best one (lowest priority first)
        best_provider = sorted(matches, key=lambda x: x.priority)[0]
        best_provider = best_provider.copy(data_source)
        self.data_providers_lookup[data_source] = best_provider

        symbol = data_source.symbol
        market = data_source.market
        time_frame = data_source.time_frame

        if DataType.OHLCV.equals(data_source.data_type):

            if symbol not in self.ohlcv_data_providers:
                self.ohlcv_data_providers[(symbol, market)] = best_provider
                self.ohlcv_data_providers_no_market[symbol] = best_provider
                self.ohlcv_data_providers_with_timeframe[
                    (symbol, market, time_frame)
                ] = best_provider
            else:
                try:
                    # If the symbol already exists, we can update the provider
                    # has a more granular timeframe
                    existing_provider = self.ohlcv_data_providers[
                        (symbol.upper(), market.upper())
                    ]
                    if existing_provider.time_frame > best_provider.time_frame:
                        self.ohlcv_data_providers[
                            (symbol.upper(), market.upper())
                        ] =\
                            best_provider

                    existing_provider = self.ohlcv_data_providers_no_market[
                        symbol
                    ]

                    if existing_provider.time_frame > best_provider.time_frame:
                        self.ohlcv_data_providers_no_market[symbol] = \
                            best_provider

                    time_frame_key = (symbol, market, data_source.time_frame)
                    self.ohlcv_data_providers_with_timeframe[
                        time_frame_key
                    ] = best_provider

                except Exception:
                    # If the existing provider does not have a time_frame
                    # attribute, we can safely ignore this
                    pass

        elif DataType.TICKER.equals(data_source.data_type):
            if symbol not in self.ticker_data_providers:
                self.ticker_data_providers[symbol] = best_provider

        return best_provider

    def get(self, data_source: DataSource) -> Optional[DataProvider]:
        """
        Get the data provider for a given data source.

        Args:
            data_source (DataSource): The data source to get the
                data provider for.

        Returns:
            DataProvider: The data provider for the market and symbol,
        """
        return self.data_providers_lookup.get(data_source, None)

    def find(self, data_source: DataSource) -> Optional[DataProvider]:
        """
        Find a data provider for a given data source.

        Args:
            data_source (DataSource): The data source to find the
                data provider for.

        Returns:
            DataProvider: The data provider for the market and symbol,
                or None if no provider is found.
        """
        return self.data_providers_lookup.get(data_source, None)

    def get_all(self) -> List[Tuple[DataSource, DataProvider]]:
        """
        Get all registered data providers with corresponding DataSource.

        Returns:
             List[Tuple[DataSource, DataProvider]]: A list of all
                data providers with corresponding data sources.
        """
        return [
            (data_source, data_provider)
            for data_source, data_provider
            in self.data_providers_lookup.items()
        ]

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

    def get_ohlcv_data_provider(
        self,
        symbol: str,
        market: Optional[str] = None,
        time_frame: Optional[str] = None
    ) -> Optional[DataProvider]:
        """
        Get the OHLCV data provider for a given symbol and market.

        Args:
            symbol (str): The symbol to get the data provider for.
            market (Optional[str]): The market to get the data provider for.
            time_frame (Optional[str]): The time frame to get the
                data provider for.

        Returns:
            DataProvider: The OHLCV data provider for the symbol and market,
                or None if no provider is found.
        """

        if market is not None and time_frame is not None:
            time_frame = TimeFrame.from_value(time_frame)
            return self.ohlcv_data_providers_with_timeframe.get(
                (symbol, market, time_frame), None
            )

        if market is None:
            # If no market is specified
            return self.ohlcv_data_providers_no_market.get(symbol, None)

        return self.ohlcv_data_providers.get((symbol, market), None)

    def get_ticker_data_provider(
        self, symbol: str, market: str
    ) -> Optional[DataProvider]:
        """
        Get the ticker data provider for a given symbol and market.

        Args:
            symbol (str): The symbol to get the data provider for.
            market (str): The market to get the data provider for.

        Returns:
            DataProvider: The ticker data provider for the symbol and market,
                or None if no provider is found.
        """
        return self.ticker_data_providers.get(symbol, None)


class DataProviderService:
    data_provider_index: DataProviderIndex = None
    backtest_mode = False

    def __init__(
        self,
        configuration_service,
        market_credential_service,
        default_data_providers: List[DataProvider] = [],
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

    def get(self, data_source: DataSource) -> Optional[DataProvider]:
        """
        Get a registered data provider by its data source.

        Args:
            data_source (DataSource): The data source to get the
            data provider for.

        Returns:
            Optional[DataProvider]: The registered data provider for
              the data source, or None if not found.
        """
        return self.data_provider_index.get(data_source)

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
        data_provider = self.data_provider_index.get(data_source=data_source)

        if data_provider is None:
            dict_data = data_source.to_dict()
            self._throw_no_data_provider_exception(dict_data)

        if self.configuration_service is not None:
            data_provider.config = self.configuration_service.get_config()

        return data_provider.get_data(
            date=date,
            start_date=start_date,
            end_date=end_date,
            save=data_source.save,
        )

    def get_ticker_data(self, symbol, market, date):
        """
        Function to get a ticker for a given data source.
        The data source should have its market and symbol defined.
        All other attributes are ignored of the data source
        """
        data_provider = self.data_provider_index.get_ticker_data_provider(
            symbol=symbol, market=market
        )

        if data_provider is None:
            ohlcv_data_provider = self.data_provider_index.\
                get_ohlcv_data_provider(
                    symbol=symbol, market=market
                )

            if ohlcv_data_provider is None:
                raise OperationalException(
                    "No ticker data provider found "
                    f"for symbol: {symbol} and market: {market} "
                    f"on date: {date}"
                )
            else:
                if self.backtest_mode:
                    data = ohlcv_data_provider.get_backtest_data(
                        backtest_index_date=date,
                    )

                    if isinstance(data, pd.DataFrame):
                        # Convert to Polars DataFrame for consistency
                        data.index.name = "Datetime"
                        data = data.reset_index()
                        data = pl.from_pandas(data)
                    entry = data[-1]
                    return {
                        "symbol": symbol,
                        "market": market,
                        "datetime": entry["Datetime"][0],
                        "open": entry["Open"][0],
                        "high": entry["High"][0],
                        "low": entry["Low"][0],
                        "close": entry["Close"][0],
                        "volume": entry["Close"][0],
                        "ask": entry["Close"][0],
                        "bid": entry["Close"][0],
                    }
                else:
                    data = ohlcv_data_provider.get_data(
                        date=date,
                    )

                    if isinstance(data, pd.DataFrame):
                        # Convert to Polars DataFrame for consistency
                        data.index.name = "Datetime"
                        data = data.reset_index()
                        data = pl.from_pandas(data)

                    entry = data[-1]
                    return {
                        "symbol": symbol,
                        "market": market,
                        "datetime": entry["Datetime"][0],
                        "open": entry["Open"][0],
                        "high": entry["High"][0],
                        "low": entry["Low"][0],
                        "close": entry["Close"][0],
                        "volume": entry["Close"][0],
                        "ask": entry["Close"][0],
                        "bid": entry["Close"][0],
                    }
        else:

            if self.backtest_mode:
                return data_provider.get_backtest_data(
                    backtest_index_date=date,
                )

            else:
                return data_provider.get_data(date=date)

    def get_ohlcv_data(
        self,
        symbol: str,
        market: str = None,
        time_frame: str = None,
        date: Optional[datetime] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        window_size: Optional[int] = None,
        pandas: bool = False,
        add_pandas_index: bool = True,
        add_datetime_column: bool = False,
    ):
        """
        Function to get OHLCV data from the data provider.

        Args:
            symbol (str): The symbol to get OHLCV data for.
            market (str): The market to get OHLCV data for.
            time_frame (str): The time frame to get OHLCV data for.
            date (datetime): The date to get OHLCV data for.
            start_date (datetime): The start date for the OHLCV data.
            end_date (datetime): The end date for the OHLCV data.
            window_size (int): The window size for the OHLCV data.
            pandas (bool): Whether to return the data as a pandas DataFrame.
            add_pandas_index (bool): Whether to add a pandas index to
                the DataFrame if pandas is True.
            add_datetime_column (bool): Whether to add a datetime column
                to the DataFrame if pandas is True.

        Returns:
            DataFrame: The OHLCV data for the given symbol and market.
        """
        data_provider = self.data_provider_index.get_ohlcv_data_provider(
            symbol=symbol,
            market=market,
            time_frame=time_frame
        )

        if data_provider is None:
            if market is not None:
                raise OperationalException(
                    "No OHLCV data provider found "
                    f"for symbol: {symbol} and market: {market}"
                )
            else:
                raise OperationalException(
                    f"No OHLCV data provider found for symbol: {symbol}"
                )

        if self.backtest_mode:
            data = data_provider.get_backtest_data(
                backtest_index_date=date,
                backtest_start_date=start_date,
                backtest_end_date=end_date,
            )
        else:
            data = data_provider.get_data(
                date=date,
                start_date=start_date,
                end_date=end_date,
            )

        if pandas:
            if isinstance(data, pl.DataFrame):
                return convert_polars_to_pandas(
                    data,
                    add_index=add_pandas_index,
                    add_datetime_column=add_datetime_column
                )
            else:
                return data

        if isinstance(data, pd.DataFrame):
            # Convert to Polars DataFrame for consistency
            data.index.name = "Datetime"
            data = data.reset_index()
            data = pl.from_pandas(data)

        return data

    def get_backtest_data(
        self,
        data_source: DataSource,
        backtest_index_date: datetime = None,
        start_date: datetime = None,
        end_date: datetime = None,
    ):
        """
        Function to get backtest data from the data provider.

        Args:
            data_source (DataSource): The data source specification that
                matches a data provider.
            backtest_index_date (datetime): The current date of the backtest.
            start_date (datetime): The start date for the data.
            end_date (datetime): The end date for the data.

        Returns:
            DataFrame: The backtest data for the given symbol and market.
        """
        data_provider = self.data_provider_index.get(data_source=data_source)

        if data_provider is None:
            self._throw_no_data_provider_exception(data_source.to_dict())

        return data_provider.get_backtest_data(
            backtest_index_date=backtest_index_date,
            backtest_start_date=start_date,
            backtest_end_date=end_date,
            data_source=data_source
        )

    def get_vectorized_backtest_data(
        self,
        data_sources: List[DataSource],
        start_date: datetime = None,
        end_date: datetime = None,
    ) -> Dict[str, Any]:
        """
        Function to get vectorized backtest data from the data provider.

        Args:
            data_sources (List[DataSource]): The data sources to get
                backtest data for.
            start_date (datetime): The start date for the backtest data.
            end_date (datetime): The end date for the backtest data.

        Returns:
            Dict[str, Any]: The vectorized backtest data for the
                given data sources.
        """
        vectorized_data = {}

        for data_source in data_sources:
            data_start_date = data_source.create_start_date_data(start_date)
            backtest_data = self.get_backtest_data(
                data_source=data_source,
                start_date=data_start_date,
                end_date=end_date,
            )
            vectorized_data[data_source.get_identifier()] = backtest_data

        return vectorized_data

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

    def register_data_provider(
        self, data_source: DataSource, data_provider: DataProvider
    ) -> DataProvider:
        """
        Function to directly register a data provider for a given data source.

        This method will not check if the data provider supports the
        data source. It will directly register the data provider in the index.

        Args:
            data_source (DataSource): The data source to register the
                data provider for.
            data_provider (DataProvider): The data provider to register.

        Returns:
            DataProvider: The registered data provider.
        """
        data_provider = data_provider.copy(data_source)
        self.data_provider_index.data_providers_lookup[data_source] = \
            data_provider
        return data_provider

    def add_data_provider(
        self, data_provider: DataProvider, priority: int = 3
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
        data_provider.config = self.configuration_service.get_config()
        self.data_provider_index.add(data_provider)

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
            logger.debug(
                "Registered data provider for data source: {data_source}"
            )

    def index_backtest_data_providers(
        self,
        data_sources: List[DataSource],
        backtest_date_range: BacktestDateRange,
        show_progress: bool = True
    ):
        """
        Index the data providers in the service.
        This will create a fast lookup index for the data providers
        based on the given parameters.

        Args:
            data_sources (List[DataSource]): The data sources to index.
            backtest_date_range (BacktestDateRange): The date range for the
                backtest data providers.
            show_progress (bool): Whether to show progress while indexing
                the data providers.

        Returns:
            None
        """

        # Filter out duplicate data_sources
        unique_data_sources = set(data_sources)

        if show_progress:

            for data_source in tqdm(
                unique_data_sources,
                desc="Registering backtest data providers for data sources",
                colour="green"
            ):
                self.data_provider_index.register_backtest_data_source(
                    data_source, backtest_date_range
                )
                logger.debug(
                    "Registered backtest "
                    f"data provider for data source: {data_source}"
                )
        else:
            for data_source in unique_data_sources:
                self.data_provider_index.register_backtest_data_source(
                    data_source, backtest_date_range
                )
                logger.debug(
                    "Registered backtest "
                    f"data provider for data source: {data_source}"
                )

        self.backtest_mode = True

    def prepare_backtest_data(
        self,
        backtest_date_range: BacktestDateRange,
        show_progress: bool = True
    ):
        """
        Prepare the backtest data for all registered data providers.

        Args:
            backtest_date_range (BacktestDateRange): The date range for the
                backtest data.
            show_progress (bool): Whether to show progress while preparing
                the backtest data.

        Raises:
            OperationalException: If no data providers are registered.

        Returns:
            None
        """

        if len(self.data_provider_index.data_providers_lookup) == 0:
            raise OperationalException(
                "No data providers registered. "
                "Please register at least one data provider before preparing "
                "backtest data."
            )

        logger.info(
            "Preparing backtest data for all registered data providers"
        )

        if show_progress:
            for data_source, data_provider in tqdm(
                self.data_provider_index.get_all(),
                desc="Preparing backtest data",
                colour="green"
            ):
                try:
                    data_provider.prepare_backtest_data(
                        backtest_start_date=backtest_date_range.start_date,
                        backtest_end_date=backtest_date_range.end_date
                    )
                except Exception as e:
                    logger.error(
                        f"Error preparing backtest data for {data_source}: {e}"
                    )
        else:
            for data_source, data_provider \
                    in self.data_provider_index.get_all():

                try:
                    data_provider.prepare_backtest_data(
                        backtest_start_date=backtest_date_range.start_date,
                        backtest_end_date=backtest_date_range.end_date
                    )
                except Exception as e:
                    logger.error(
                        f"Error preparing backtest data for {data_source}: {e}"
                    )

    def get_data_files(self):
        """
        Function to get the data files for the market data sources.

        Returns:
            List[str]: A list of file paths for the data files.
        """
        data_files = []

        for market_data_source in self.data_provider_index.data_providers:
            if hasattr(market_data_source, 'file_path') and \
                    market_data_source.file_path is not None:
                data_files.append(market_data_source.file_path)

        return data_files

    def get_all_registered_data_providers(self) -> List[DataProvider]:
        """
        Function to get all registered data providers.

        Returns:
            List[DataProvider]: A list of all registered data providers.
        """
        return self.data_provider_index.get_all()

    def reset(self):
        """
        Function to reset all the data providers and the data provider
        lookup index.
        """
        self.data_provider_index.reset()
        self.backtest_mode = False
