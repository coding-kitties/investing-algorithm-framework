import logging
from collections import defaultdict
from typing import List, Union

from investing_algorithm_framework.domain import ImproperlyConfigured, \
    PortfolioProvider

logger = logging.getLogger("investing_algorithm_framework")


class PortfolioProviderLookup:
    """
    Efficient lookup for portfolio providers based on market in O(1) time.
    """
    def __init__(self):
        self.portfolio_providers = []

        # These will be our lookup tables
        self.portfolio_provider_lookup = defaultdict()

    def add_portfolio_provider(self, portfolio_provider: PortfolioProvider):
        """
        Add a portfolio provider to the lookup table.

        Args:
            portfolio_provider (PortfolioProvider): The portfolio provider
                to be added.

        Returns:
            None
        """
        self.portfolio_providers.append(portfolio_provider)

    def register_portfolio_provider_for_market(self, market) -> None:
        """
        Register a portfolio provider for a specific market.
        This method will create a lookup table for efficient access to
        portfolio providers based on market. It will use the
        portfolio providers that are currently registered in the
        portfolio_providers list. The lookup table will be a dictionary
        where the key is the market and the value is the portfolio provider.

        This method will also check if the portfolio provider supports
        the market. If no portfolio provider is found for the market,
        it will raise an ImproperlyConfigured exception.

        If multiple portfolio providers are found for the market,
        it will sort them by priority and pick the best one.

        Args:
            market:

        Returns:
            None
        """
        matches = []

        for portfolio_provider in self.portfolio_providers:

            if portfolio_provider.supports_market(market):
                matches.append(portfolio_provider)

        if len(matches) == 0:
            raise ImproperlyConfigured(
                f"No portfolio provider found for market "
                f"{market}. Cannot configure portfolio."
                f" Please make sure that you have registered a portfolio "
                f"provider for the market you are trying to use"
            )

        # Sort by priority and pick the best one
        best_provider = sorted(matches, key=lambda x: x.priority)[0]
        self.portfolio_provider_lookup[market] = best_provider

    def get_portfolio_provider(self, market) -> Union[PortfolioProvider, None]:
        """
        Get the portfolio provider for a specific market.
        This method will return the portfolio provider for the given market.
        If no portfolio provider is found, it will return None.

        Args:
            market:

        Returns:
            PortfolioProvider: The portfolio provider for the given market.
        """
        return self.portfolio_provider_lookup.get(market, None)

    def get_all(self) -> List[PortfolioProvider]:
        """
        Get all portfolio providers.
        This method will return all portfolio providers that are currently
        registered in the portfolio_providers list.

        Returns:
            List[PortfolioProvider]: A list of all portfolio providers.
        """
        return self.portfolio_providers

    def reset(self):
        """
        Function to reset the order executor lookup table

        Returns:
            None
        """
        self.portfolio_provider_lookup = defaultdict()
        self.portfolio_providers = []
