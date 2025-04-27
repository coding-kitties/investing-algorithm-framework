from .ccxt import CCXTDataProvider


def get_default_data_providers():
    """
    Function to get the default data providers.

    Returns:
        list: List of default data providers.
    """
    return [
        CCXTDataProvider(),
    ]


__all__ = [
    'CCXTDataProvider',
    'get_default_data_providers',
]
