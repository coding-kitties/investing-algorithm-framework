from abc import ABC, abstractmethod


class PortfolioProvider(ABC):
    """
    Abstract base class for portfolio providers. The PortfolioProvider class
    is responsible for managing and providing access to trading portfolios.

    Attributes:
        portfolio_id (str): The unique identifier for the portfolio.
        user_id (str): The unique identifier for the user associated
            with the portfolio.
        balance (float): The current balance of the portfolio.
        assets (dict): A dictionary containing the assets in the
            portfolio and their quantities.
    """

    @abstractmethod
    def get_order(self, order_id: str):
        """
        Fetches an order by its ID.

        Args:
            order_id (str): The unique identifier for the order.

        Returns:
            Order: The order object.
        """
        pass

    @abstractmethod
    def get_orders(self):
        """
        Fetches all orders in the portfolio.

        Returns:
            List[Order]: A list of order objects.
        """
        pass

    @abstractmethod
    def get_position(self, position_id: str):
        """
        Fetches a position by its ID.

        Args:
            position_id (str): The unique identifier for the position.

        Returns:
            Position: The position object.
        """
        pass

    @abstractmethod
    def get_positions(self):
        """
        Fetches all positions in the portfolio.

        Returns:
            List[Position]: A list of position objects.
        """
        pass
