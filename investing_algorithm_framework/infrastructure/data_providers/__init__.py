from .ccxt import CCXTOHLCVDataProvider
from .csv import CSVOHLCVDataProvider
from .pandas import PandasOHLCVDataProvider


def get_default_data_providers():
    """
    Function to get the default data providers.

    Returns:
        list: List of default data providers.
    """
    return [
        CCXTOHLCVDataProvider(),
    ]


def get_default_ohlcv_data_providers():
    """
    Function to get the default OHLCV data providers.

    Returns:
        list: List of default OHLCV data providers.
    """
    return [
        CCXTOHLCVDataProvider(),
    ]


__all__ = [
    'CSVOHLCVDataProvider',
    'CCXTOHLCVDataProvider',
    'get_default_data_providers',
    'get_default_ohlcv_data_providers',
    'PandasOHLCVDataProvider',
]
