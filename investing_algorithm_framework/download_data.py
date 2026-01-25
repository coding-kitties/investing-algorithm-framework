from dataclasses import dataclass
from pathlib import Path
from dateutil import parser
from datetime import timezone, datetime
import os
import pandas
import polars
from typing import Union, Optional
from investing_algorithm_framework.services import DataProviderService, \
    ConfigurationService, MarketCredentialService
from investing_algorithm_framework.infrastructure import \
    get_default_data_providers
from investing_algorithm_framework.domain import DataSource, \
    OperationalException, DataType


@dataclass
class DownloadResult:
    """
    Result container for download function.

    Attributes:
        data: The downloaded data as a pandas or polars DataFrame.
        path: The file path where the data was saved (None if not saved).
    """
    data: Union[pandas.DataFrame, polars.DataFrame]
    path: Optional[Path] = None


def create_data_storage_path(
    symbol: str,
    market: str,
    time_frame: str,
    start_date: datetime,
    end_date: datetime,
    storage_path: str,
    data_type: str = "ohlcv",
) -> Path:
    """
    Create the file path where data would be stored.

    This function generates the same path that the download function
    uses when saving data, allowing you to reference the file later.

    Args:
        symbol: Trading pair (e.g., "BTC/EUR")
        market: Market identifier (e.g., "BITVAVO")
        time_frame: Time frame (e.g., "2h", "4h", "1d")
        start_date: Start date of the data
        end_date: End date of the data
        storage_path: Base directory for storing files
        data_type: Type of data (default: "ohlcv")

    Returns:
        Path: The full file path where data would be stored.
    """
    datetime_format = "%Y-%m-%d-%H-%M"
    symbol_formatted = symbol.upper().replace('/', '-')
    start_date_str = start_date.strftime(datetime_format)
    end_date_str = end_date.strftime(datetime_format)
    filename = (
        f"{data_type.upper()}_{symbol_formatted}_{market.upper()}_"
        f"{time_frame}_{start_date_str}_{end_date_str}.csv"
    )
    return Path(storage_path) / filename


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
    save_to: Union[str, Path] = None,
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
        save_to (str): The path to save the downloaded data. If provided,
            it overrides storage_path.
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


def download_v2(
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
) -> DownloadResult:
    """
    Download market data and return both the DataFrame and file path.

    This is an improved version of download() that returns a DownloadResult
    containing both the downloaded data and the file path where it was saved.

    Args:
        symbol: Trading pair (e.g., "BTC/EUR")
        market: Market identifier (e.g., "BITVAVO")
        time_frame: Time frame (e.g., "2h", "4h", "1d")
        data_type: Type of data (default: "ohlcv")
        start_date: Start date for data range
        end_date: End date for data range
        date: Specific date for data download
        window_size: Size of the data window
        pandas: Whether to return the data as a pandas DataFrame
        save: Whether to save the data to disk
        storage_path: Base directory for storing files

    Returns:
        DownloadResult with .data (DataFrame) and .path (Path or None)
    """
    # Parse dates if they are strings
    parsed_start_date = start_date
    parsed_end_date = end_date

    if parsed_start_date is not None and isinstance(parsed_start_date, str):
        parsed_start_date = parser.parse(parsed_start_date)
        parsed_start_date = parsed_start_date.replace(tzinfo=timezone.utc)

    if parsed_end_date is not None and isinstance(parsed_end_date, str):
        parsed_end_date = parser.parse(parsed_end_date)
        parsed_end_date = parsed_end_date.replace(tzinfo=timezone.utc)

    # Download the data using the existing function
    data = download(
        symbol=symbol,
        market=market,
        date=date,
        time_frame=time_frame,
        data_type=data_type,
        start_date=start_date,
        end_date=end_date,
        window_size=window_size,
        pandas=pandas,
        save=save,
        storage_path=storage_path,
    )

    # Determine the file path if data was saved
    file_path = None
    if save and storage_path and parsed_start_date and parsed_end_date:
        data_type_str = data_type.value \
            if isinstance(data_type, DataType) else data_type
        file_path = create_data_storage_path(
            symbol=symbol,
            market=market,
            time_frame=time_frame,
            start_date=parsed_start_date,
            end_date=parsed_end_date,
            storage_path=str(storage_path),
            data_type=data_type_str,
        )

    return DownloadResult(data=data, path=file_path)

