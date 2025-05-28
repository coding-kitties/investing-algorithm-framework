from dateutil import parser
import pandas
import polars
from typing import Union
from investing_algorithm_framework.services import DataProviderService, \
    ConfigurationService, MarketCredentialService
from investing_algorithm_framework.infrastructure import \
    get_default_data_providers, get_default_ohlcv_data_providers


def download(
    symbol: str,
    market=None,
    date=None,
    time_frame: str = None,
    data_type: str = "ohlcv",
    start_date: str = None,
    end_date: str = None,
    window_size: int = 200,
    pandas: bool = True,
    save: bool = True,
    storage_path: str = None,
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
        market_credentials_service=market_credential_service,
        default_ohlcv_data_providers=get_default_ohlcv_data_providers()
    )

    if start_date is not None and isinstance(start_date, str):
        start_date = parser.parse(start_date)

    if end_date is not None and isinstance(end_date, str):
        end_date = parser.parse(end_date)

    if date is not None and isinstance(date, str):
        date = parser.parse(date)

    return data_provider_service.get_data(
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
