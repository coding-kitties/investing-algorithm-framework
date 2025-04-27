from abc import ABC, abstractmethod


class OrderExecutor(ABC):
    """
    Abstract base class for order executors. The OrderExecutor class is
    responsible for executing orders in a trading algorithm.

    Attributes:
        market (str): The market in which the order will be executed

    """

    @property
    def market_credentials(self):
        """
        Returns the market credentials for the order executor.

        Returns:
            dict: A dictionary containing the market credentials.
        """
        return self._market_credentials

    @market_credentials.setter
    def market_credentials(self, credentials):
        """
        Sets the market credentials for the order executor.

        Args:
            value (dict): A dictionary containing the market credentials.
        """
        self._market_credentials = credentials

    @abstractmethod
    def execute_order(self, order):
        """
        Executes an order.

        Args:
            order: The order to be executed


        Returns:
            Order: Instance of the executed order.
        """
        raise NotImplementedError(
            "Subclasses must implement this method."
        )

    @abstractmethod
    def cancel_order(self, order):
        """
        Cancels an order.

        Args:
            order: The order to be canceled

        Returns:
            Order: Instance of the canceled order.
        """
        raise NotImplementedError(
            "Subclasses must implement this method."
        )
