from abc import ABC, abstractmethod

from investing_algorithm_framework.domain import Order


class OrderExecutor(ABC):
    """
    Abstract base class for order executors. The OrderExecutor class is
    responsible for executing orders in a trading algorithm.

    Attributes:
        _priority (int): The priority of the order executor compared to
            other order executors. The lower the number, the higher the
            priority. The framework will use this priority when searching
            for an order executor for a specific market.
    """

    def __init__(self, priority=1):
        self._priority = priority

    @property
    def priority(self):
        """
        Returns the priority of the order executor.
        """
        return self._priority

    @abstractmethod
    def execute_order(self, portfolio, order, market_credential) -> Order:
        """
        Executes an order for a given portfolio. The order executor should
        create an order on the exchange or broker and return an order object
        that reflects the order on the exchange or broker. This should be
        done by setting the external_id of the order to the id of the order
        on the exchange or broker.

        !Important: This function should not throw an exception if the order
        is not successfully executed. Instead, it should return an order
        instance with the status set to OrderStatus.FAILED.

        Args:
            order: The order to be executed
            portfolio: The portfolio in which the order will be executed
            market_credential: The market credential to use for the order

        Returns:
            Order: Instance of the executed order. The order instance
            should copy the id of the order that has been provided as a
        """
        raise NotImplementedError(
            "Subclasses must implement this method."
        )

    @abstractmethod
    def cancel_order(self, portfolio, order, market_credential) -> Order:
        """
        Cancels an order for a given portfolio. The order executor should
        cancel the order on the exchange or broker and return an order
        object that reflects the order on the exchange or broker.

        Args:
            order: The order to be canceled
            portfolio: The portfolio in which the order was executed
            market_credential: The market credential to use for the order

        Returns:
            Order: Instance of the canceled order.
        """
        raise NotImplementedError(
            "Subclasses must implement this method."
        )

    @abstractmethod
    def supports_market(self, market):
        """
        Checks if the order executor supports the given market.

        Args:
            market: The market to check

        Returns:
            bool: True if the order executor supports the market, False
                otherwise.
        """
        raise NotImplementedError(
            "Subclasses must implement this method."
        )

    def __repr__(self):
        """
        Returns a string representation of the order executor.
        """
        return f"{self.__class__.__name__}(priority={self._priority})"
