from .ccxt_portfolio_provider import CCXTPortfolioProvider


def get_default_portfolio_providers():
    """
    Function to get the default portfolio providers.

    Returns:
        list: List of default portfolio providers.
    """
    return [
        CCXTPortfolioProvider(),
    ]


__all__ = [
    "CCXTPortfolioProvider",
    "get_default_portfolio_providers",
]
