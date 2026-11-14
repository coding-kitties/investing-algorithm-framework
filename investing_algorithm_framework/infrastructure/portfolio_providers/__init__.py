from .ccxt_portfolio_provider import CCXTPortfolioProvider
from .paper_trading_portfolio_provider import PaperTradingPortfolioProvider


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
    "PaperTradingPortfolioProvider",
    "get_default_portfolio_providers",
]
