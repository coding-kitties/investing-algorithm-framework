import logging

from investing_algorithm_framework.services.repository_service import \
    RepositoryService


logger = logging.getLogger("investing_algorithm_framework")


class PositionService(RepositoryService):

    def __init__(self, repository, portfolio_repository):
        """
        Initialize the PositionService.

        Args:
            repository (Repository): The repository to use for storing
                positions.
            portfolio_repository (Repository): The repository to use for
                storing portfolios.
        """
        super().__init__(repository)
        self.portfolio_repository = portfolio_repository

    def update(self, position_id, data):
        """
        Function to update a position.

        Args:
            position_id (str): The id of the position to update.
            data (dict): The data to update the position with.

        Returns:
            Position: The updated position.
        """
        position = self.get(position_id)
        logger.info(
            f"Updating position {position_id} ({position.get_symbol()}) "
            f"with data: {data}"
        )
        return super().update(position_id, data)

    def update_positions_with_created_buy_order(self, order):
        """
        Function to update positions with created order.
        If the order is filled then also the amount of the position
        is updated.

        Args:
            order (Order): The order that has been created.

        Returns:
            None
        """
        position = self.get(order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        size = order.get_size()
        filled = order.get_filled()

        logger.info(
            f"Syncing trading symbol {portfolio.get_trading_symbol()} "
            "position with created buy "
            f"order {order.get_id()} with size {size}"
        )
        trading_symbol_position = self.find(
            {
                "portfolio": portfolio.id,
                "symbol": portfolio.trading_symbol
            }
        )
        self.update(
            trading_symbol_position.id,
            {
                "amount": trading_symbol_position.get_amount() - size
            }
        )

        if filled > 0:
            logger.info(
                f"Syncing position {position.get_symbol()} with created buy "
                f"order {order.get_id()} with filled size {order.get_filled()}"
            )
            self.update(
                position.id,
                {
                    "amount": position.get_amount() + order.get_filled(),
                    "cost": position.get_cost() + size,
                }
            )

    def update_positions_with_buy_order_filled(self, order, filled_amount):
        """
        Function to update positions with filled order.

        Args:
            order (Order): The order that has been filled.
            filled_amount (float): The amount that has been filled.

        Returns:
            None
        """
        # Calculate the filled size
        filled_size = filled_amount * order.get_price()

        if filled_amount <= 0:
            return

        logger.info(
            f"Syncing position with filled buy "
            f"order {order.get_id()} with filled amount "
            f"{filled_amount}"
        )

        # Update the position
        position = self.get(order.position_id)
        self.update(
            position.id,
            {
                "amount": position.get_amount() + filled_amount,
                "cost":
                    position.get_cost() + filled_size
            }
        )

    def update_positions_with_created_sell_order(self, order):
        """
        Function to update positions with created order.
        If the order is filled then also the amount of the position
        is updated.

        Args:
            order (Order): The order that has been created.

        Returns:
            None
        """
        position = self.get(order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        filled = order.get_filled()
        filled_size = filled * order.get_price()

        logger.info(
            f"Syncing position {position.get_symbol()} "
            "with created sell "
            f"order {order.get_id()} with amount {order.get_amount()}"
        )
        self.update(
            position.id,
            {
                "amount": position.get_amount() - order.get_amount(),
            }
        )

        if filled > 0:

            logger.info(
                f"Syncing trading symbol {portfolio.get_trading_symbol()} "
                "position with created sell "
                f"order {order.get_id()} with filled size {filled_size}"
            )
            trading_symbol_position = self.find(
                {
                    "portfolio": portfolio.id,
                    "symbol": portfolio.trading_symbol
                }
            )
            self.update(
                trading_symbol_position.id,
                {
                    "amount":
                        trading_symbol_position.get_amount() + filled_size
                }
            )

    def update_positions_with_sell_filled_order(self, order, filled_amount):
        """
        Function to update positions with filled order.

        Args:
            order:
            filled_amount:

        Returns:

        """
        position = self.get(order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        trading_symbol_position = self.find(
            {
                "portfolio": portfolio.id,
                "symbol": portfolio.trading_symbol
            }
        )
        filled_size = filled_amount * order.get_price()

        logger.info(
            "Syncing trading symbol position "
            f"{portfolio.get_trading_symbol()} "
            f"with filled sell "
            f"order {order.get_id()} with filled size "
            f"{filled_size} {portfolio.get_trading_symbol()}"
        )
        # Update the trading symbol position
        self.update(
            trading_symbol_position.id,
            {
                "amount":
                    trading_symbol_position.get_amount() + filled_size
            }
        )
