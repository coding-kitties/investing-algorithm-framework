from .ccxt import CCXTOHLCVDataProvider, CCXTTickerDataProvider
from .csv import CSVOHLCVDataProvider, CSVTickerDataProvider
from .pandas import PandasOHLCVDataProvider
from .yahoo import YahooOHLCVDataProvider


def get_default_data_providers():
    """
    Function to get the default data providers.

    Returns:
        list: List of default data providers.
    """
    return [
        CCXTOHLCVDataProvider(),
        CCXTTickerDataProvider(),
        YahooOHLCVDataProvider(),
    ]


def get_default_ohlcv_data_providers():
    """
    Function to get the default OHLCV data providers.

    Returns:
        list: List of default OHLCV data providers.
    """
    return [
        CCXTOHLCVDataProvider(),
        YahooOHLCVDataProvider(),
    ]


__all__ = [
    'CSVOHLCVDataProvider',
    'CSVTickerDataProvider',
    'CCXTOHLCVDataProvider',
    'CCXTTickerDataProvider',
    'get_default_data_providers',
    'get_default_ohlcv_data_providers',
    'PandasOHLCVDataProvider',
    'YahooOHLCVDataProvider',
]
