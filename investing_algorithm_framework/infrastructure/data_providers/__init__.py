from .ccxt import CCXTOHLCVDataProvider, CCXTTickerDataProvider
from .csv import CSVOHLCVDataProvider, CSVTickerDataProvider
from .pandas import PandasOHLCVDataProvider
from .ohlcv_base import OHLCVDataProviderBase


def _make_optional_provider_placeholder(name, package, extra):
    """Create a placeholder class that raises ImportError on instantiation."""

    class _Placeholder:
        def __init__(self, *args, **kwargs):
            raise ImportError(
                f"{package} is required for {name}. "
                f"Install it with: "
                f"pip install investing-algorithm-framework[{extra}]"
            )

    _Placeholder.__name__ = name
    _Placeholder.__qualname__ = name
    return _Placeholder


# Optional provider imports — only available when extras are installed
try:
    from .yahoo import YahooOHLCVDataProvider
    _yahoo_available = True
except ImportError:
    YahooOHLCVDataProvider = _make_optional_provider_placeholder(
        "YahooOHLCVDataProvider", "yfinance", "yahoo"
    )
    _yahoo_available = False

try:
    from .alpha_vantage import AlphaVantageOHLCVDataProvider
    _alpha_vantage_available = True
except ImportError:
    AlphaVantageOHLCVDataProvider = _make_optional_provider_placeholder(
        "AlphaVantageOHLCVDataProvider", "alpha_vantage", "alpha_vantage"
    )
    _alpha_vantage_available = False

try:
    from .polygon import PolygonOHLCVDataProvider
    _polygon_available = True
except ImportError:
    PolygonOHLCVDataProvider = _make_optional_provider_placeholder(
        "PolygonOHLCVDataProvider", "polygon-api-client", "polygon"
    )
    _polygon_available = False


def get_default_data_providers():
    """
    Function to get the default data providers.

    Returns:
        list: List of default data providers.
    """
    providers = [
        CCXTOHLCVDataProvider(),
        CCXTTickerDataProvider(),
    ]

    if _yahoo_available:
        providers.append(YahooOHLCVDataProvider())

    if _alpha_vantage_available:
        providers.append(AlphaVantageOHLCVDataProvider())

    if _polygon_available:
        providers.append(PolygonOHLCVDataProvider())

    return providers


def get_default_ohlcv_data_providers():
    """
    Function to get the default OHLCV data providers.

    Returns:
        list: List of default OHLCV data providers.
    """
    providers = [
        CCXTOHLCVDataProvider(),
    ]

    if _yahoo_available:
        providers.append(YahooOHLCVDataProvider())

    if _alpha_vantage_available:
        providers.append(AlphaVantageOHLCVDataProvider())

    if _polygon_available:
        providers.append(PolygonOHLCVDataProvider())

    return providers


__all__ = [
    'CSVOHLCVDataProvider',
    'CSVTickerDataProvider',
    'CCXTOHLCVDataProvider',
    'CCXTTickerDataProvider',
    'get_default_data_providers',
    'get_default_ohlcv_data_providers',
    'OHLCVDataProviderBase',
    'PandasOHLCVDataProvider',
    'YahooOHLCVDataProvider',
    'AlphaVantageOHLCVDataProvider',
    'PolygonOHLCVDataProvider',
]
