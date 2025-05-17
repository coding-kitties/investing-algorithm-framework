from typing import Union
from abc import ABC, abstractmethod

from investing_algorithm_framework.domain import Order, Position


class PortfolioProvider(ABC):
    """
    Abstract base class for portfolio providers. The PortfolioProvider class
    is responsible for managing and providing access to trading portfolios.

    Attributes:
        priority (int): The priority of the portfolio provider compared to
            other portfolio providers. The lower the number, the higher the
            priority. The framework will use this priority when searching
            for a portfolio provider for a specific symbol or market.
    """

    def __init__(self, priority=1):
        self._priority = priority

    @property
    def priority(self):
        """
        Returns the priority of the portfolio provider.
        """
        return self._priority

    @priority.setter
    def priority(self, value: int):
        """
        Sets the priority of the portfolio provider.
        """
        self._priority = value

    @abstractmethod
    def get_order(
        self, portfolio, order, market_credential
    ) -> Union[Order, None]:
        """
        Function to get an order from the exchange or broker. The returned
        should be an order object that reflects the current state of the
        order on the exchange or broker.

        !IMPORTANT: This function should return None if the order is
        not found or if the order is not available on the
        exchange or broker. Please do not throw an exception if the
        order is not found.

        Args:
            portfolio: Portfolio object
            order: Order object from the database
            market_credential: Market credential object

        Returns:
            Order: Order object reflecting the order on the exchange or broker
        """
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    def get_position(
        self, portfolio, symbol, market_credential
    ) -> Union[Position, None]:
        """
        Function to get the position for a given symbol in the portfolio.
        The returned position should be an object that reflects the current
        state of the position on the exchange or broker.

        !IMPORTANT: This function should return None if the position is
        not found or if the position is not available on the
        exchange or broker. Please do not throw an exception if the
        position is not found.

        Args:
            portfolio: Portfolio object
            symbol: Symbol object
            market_credential: MarketCredential object

        Returns:
            float: Position for the given symbol in the portfolio
        """
        raise NotImplementedError("Subclasses must implement this method.")

    @abstractmethod
    def supports_market(self, market) -> bool:
        """
        Function to check if the market is supported by the portfolio
        provider.

        Args:
            market: Market object

        Returns:
            bool: True if the market is supported, False otherwise
        """
        raise NotImplementedError("Subclasses must implement this method.")

    def __repr__(self):
        return f"{self.__class__.__name__}(priority={self.priority})"
