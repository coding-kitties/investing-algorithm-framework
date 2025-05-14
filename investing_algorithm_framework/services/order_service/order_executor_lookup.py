from collections import defaultdict
from typing import List

from investing_algorithm_framework.domain import OrderExecutor, \
    ImproperlyConfigured


class OrderExecutorLookup:
    """
    Efficient lookup for order executors based on market in O(1) time.

    Attributes:
        order_executors (List[OrderExecutor]): List of order executors
        order_executor_lookup (dict): Dictionary to store the lookup
            for order executors based on market.
    """
    def __init__(self, order_executors=[]):
        self.order_executors = order_executors

        # These will be our lookup tables
        self.order_executor_lookup = defaultdict()

    def add_order_executor(self, order_executor: OrderExecutor):
        """
        Add an order executor to the lookup.

        Args:
            order_executor (OrderExecutor): The order executor to be added.

        Returns:
            None
        """
        self.order_executors.append(order_executor)

    def register_order_executor_for_market(self, market) -> None:
        """
        Register an order executor for a specific market.
        This method will create a lookup table for efficient access to
        order executors based on market. It will use the
        order executors that are currently registered in the
        order_executors list. The lookup table will be a dictionary
        where the key is the market and the value is the portfolio provider.

        This method will also check if the portfolio provider supports
        the market. If no portfolio provider is found for the market,
        it will raise an ImproperlyConfigured exception.

        If multiple order executors are found for the market,
        it will sort them by priority and pick the best one.

        Args:
            market:

        Returns:
            None
        """
        matches = []

        for order_executor in self.order_executors:

            if order_executor.supports_market(market):
                matches.append(order_executor)

        if len(matches) == 0:
            raise ImproperlyConfigured(
                f"No portfolio provider found for market "
                f"{market}. Cannot configure portfolio."
                f" Please make sure that you have registered a portfolio "
                f"provider for the market you are trying to use"
            )

        # Sort by priority and pick the best one
        best_provider = sorted(matches, key=lambda x: x.priority)[0]
        self.order_executor_lookup[market] = best_provider

    def get_order_executor(self, market: str):
        """
        Get the order executor for a specific market.
        This method will return the order executor for the market
        that was registered in the lookup table. If no order executor
        was found for the market, it will return None.

        Args:
            market:

        Returns:
            OrderExecutor: The order executor for the market.
        """
        return self.order_executor_lookup.get(market, None)

    def get_all(self) -> List[OrderExecutor]:
        """
        Get all order executors.
        This method will return all order executors that are currently
        registered in the order_executors list.

        Returns:
            List[OrderExecutor]: A list of all order executors.
        """
        return self.order_executors

    def reset(self):
        """
        Function to reset the order executor lookup table

        Returns:
            None
        """
        self.order_executor_lookup = defaultdict()
        self.order_executors = []
