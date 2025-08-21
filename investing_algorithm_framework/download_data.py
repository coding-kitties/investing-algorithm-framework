from pathlib import Path
from dateutil import parser
from datetime import timezone, datetime
import pandas
import polars
from typing import Union
from investing_algorithm_framework.services import DataProviderService, \
    ConfigurationService, MarketCredentialService
from investing_algorithm_framework.infrastructure import \
    get_default_data_providers
from investing_algorithm_framework.domain import DataSource, \
    OperationalException, DataType


def download(
    symbol: str,
    market: str = None,
    date: Union[datetime, str] = None,
    time_frame: str = None,
    data_type: Union[str, DataType] = DataType.OHLCV,
    start_date: Union[datetime, str] = None,
    end_date: Union[datetime, str] = None,
    window_size: int = 200,
    pandas: bool = True,
    save: bool = True,
    storage_path: Union[str, Path] = None,
) -> Union[pandas.DataFrame, polars.DataFrame]:
    """
    Download market data from the specified source. This function
    uses the MarketDataSourceService to get the data provider
    for the given set of parameters.

    Args:
        symbol (str): The symbol to download data for.
        market (str): The market to download data from.
        data_type (str): The type of data to
            download (e.g., "ohlcv", "ticker").
        start_date (str): The start date for the data download.
        end_date (str): The end date for the data download.
        window_size (int): The size of the data window.
        pandas (bool): Whether to return the data as a pandas DataFrame.
        save (bool): Whether to save the downloaded data.
        storage_path (str): The directory to save the downloaded data.
        time_frame (str): The time frame for the data download.
        date (str): The date for the data download.
        window_size (int): The size of the data window.
        pandas (bool): Whether to return the data as a pandas DataFrame.

    Returns:
        None
    """
    configuration_service = ConfigurationService()
    market_credential_service = MarketCredentialService()
    data_provider_service = DataProviderService(
        default_data_providers=get_default_data_providers(),
        configuration_service=configuration_service,
        market_credential_service=market_credential_service,
    )

    if start_date is not None and isinstance(start_date, str):
        start_date = parser.parse(start_date)
        start_date = start_date.replace(tzinfo=timezone.utc)

    if end_date is not None and isinstance(end_date, str):
        end_date = parser.parse(end_date)
        end_date = end_date.replace(tzinfo=timezone.utc)

    if date is not None and isinstance(date, str):
        date = parser.parse(date)
        date = date.replace(tzinfo=timezone.utc)

    # Check if all the datetime parameters are in UTC
    if date is not None \
            and (date.tzinfo is None or date.tzinfo != timezone.utc):
        raise OperationalException("Date must be a UTC datetime object")

    if start_date is not None \
            and (
                start_date.tzinfo is None or start_date.tzinfo != timezone.utc
            ):
        raise OperationalException("Start date must be a UTC datetime object")

    if end_date is not None \
            and (end_date.tzinfo is None or end_date.tzinfo != timezone.utc):
        raise OperationalException("End date must be a UTC datetime object")

    data_source = DataSource(
        symbol=symbol,
        market=market,
        data_type=data_type,
        time_frame=time_frame,
        date=date,
        start_date=start_date,
        end_date=end_date,
        window_size=window_size,
        pandas=pandas,
        save=save,
        storage_path=storage_path
    )
    data_provider_service.index_data_providers(
        data_sources=[data_source]
    )
    return data_provider_service.get_data(
        data_source=data_source,
        date=date,
        start_date=start_date,
        end_date=end_date,
    )
