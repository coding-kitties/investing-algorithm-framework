import logging

from investing_algorithm_framework.domain import PositionMode
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
        Reserve trading-symbol balance for a freshly-created buy order.

        v9.0 (#431) \u2014 this method now only handles the reservation
        side: it subtracts the reserved size from the trading-symbol
        position. The target-position bump (and any cost accounting)
        for already-filled portions is handled by
        :meth:`update_positions_with_buy_order_filled` via the
        standard fill-handling path in
        :meth:`OrderService._sync_with_buy_order_filled`.

        Args:
            order (Order): The order that has been created.

        Returns:
            None
        """
        position = self.get(order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        size = order.get_size()

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

    def update_positions_with_buy_order_filled(
        self, order, filled_amount, position_mode=PositionMode.NETTING
    ):
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
        if PositionMode(position_mode) == PositionMode.HEDGE:
            self.update(
                position.id,
                {
                    "long_amount": position.long_amount + filled_amount,
                    "long_cost": position.long_cost + filled_size,
                }
            )
            return
        self.update(
            position.id,
            {
                "amount": position.get_amount() + filled_amount,
                "cost":
                    position.get_cost() + filled_size
            }
        )

    def update_positions_with_created_sell_order(
        self, order, position_mode=PositionMode.NETTING
    ):
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
        if PositionMode(position_mode) == PositionMode.HEDGE:
            self.update(
                position.id,
                {"long_amount": position.long_amount - order.get_amount()}
            )
        else:
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

    # ------------------------------------------------------------------
    # #434 phase 2 — SHORT / COVER position sync.
    #
    # Position model: short positions carry a NEGATIVE ``amount`` on
    # the target-symbol position. A SHORT fill drives the position
    # further negative; a COVER fill moves it back toward zero.
    # ------------------------------------------------------------------

    def update_positions_with_created_short_order(self, order):
        """Reserve trading-symbol collateral for a freshly-created
        short order. Cash-side semantics are identical to a BUY
        reservation (``amount * reservation_price`` is removed from
        the trading-symbol position) — the target position is not
        touched at creation time; it only moves negative on the
        first fill.
        """
        position = self.get(order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        size = order.get_size()

        logger.info(
            f"Syncing trading symbol {portfolio.get_trading_symbol()} "
            f"position with created short order {order.get_id()} "
            f"with collateral {size}"
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

    def update_positions_with_short_order_filled(
        self, order, filled_amount, position_mode=PositionMode.NETTING
    ):
        """Update the target position when a SHORT order fills:
        decrement (i.e. drive further negative) by ``filled_amount``.

        Cost accounting on the target position uses the proceeds
        (``filled_amount * fill_price``) as a positive cost — the
        position's ``cost`` field on short positions represents the
        gross proceeds captured at entry (so net_gain math stays
        symmetric with the long path).
        """
        if filled_amount is None or filled_amount <= 0:
            return

        fill_price = order.get_price()
        if fill_price is None:
            fill_price = 0
        filled_size = filled_amount * fill_price

        logger.info(
            f"Syncing position with filled short order {order.get_id()} "
            f"filled amount {filled_amount}"
        )
        position = self.get(order.position_id)
        if PositionMode(position_mode) == PositionMode.HEDGE:
            self.update(
                position.id,
                {
                    "short_amount": position.short_amount + filled_amount,
                    "short_cost": position.short_cost + filled_size,
                }
            )
            return
        self.update(
            position.id,
            {
                "amount": position.get_amount() - filled_amount,
                "cost": position.get_cost() + filled_size,
            }
        )

    def update_positions_with_created_cover_order(self, order):
        """Reserve trading-symbol cash for a freshly-created cover
        order. COVER spends cash to buy the short back, so the
        reservation mirrors a BUY (``amount * reservation_price``
        locked on the trading-symbol position).
        """
        position = self.get(order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        size = order.get_size()

        logger.info(
            f"Syncing trading symbol {portfolio.get_trading_symbol()} "
            f"position with created cover order {order.get_id()} "
            f"with reserved cash {size}"
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

    def update_positions_with_cover_order_filled(
        self, order, filled_amount, position_mode=PositionMode.NETTING
    ):
        """Update the target position when a COVER order fills:
        increment (toward zero) by ``filled_amount``. Reduces the
        position's ``cost`` proportionally so net_gain stays
        consistent for partial covers.
        """
        if filled_amount is None or filled_amount <= 0:
            return

        position = self.get(order.position_id)
        if PositionMode(position_mode) == PositionMode.HEDGE:
            # Guard against a short leg already closed by a concurrent
            # fill (e.g. two pending COVER orders on the same symbol).
            fraction = (
                filled_amount / position.short_amount
                if position.short_amount else 0
            )
            self.update(
                position.id,
                {
                    "short_amount": position.short_amount - filled_amount,
                    "short_cost": position.short_cost * (1 - fraction),
                }
            )
            return
        position_amount = position.get_amount() or 0

        # Scale the cost reduction by the fraction of the open short
        # being closed in this fill.
        if position_amount < 0:
            fraction = filled_amount / abs(position_amount)
        else:
            fraction = 0
        cost_reduction = (position.get_cost() or 0) * fraction

        logger.info(
            f"Syncing position with filled cover order {order.get_id()} "
            f"filled amount {filled_amount}"
        )
        self.update(
            position.id,
            {
                "amount": position.get_amount() + filled_amount,
                "cost": (position.get_cost() or 0) - cost_reduction,
            }
        )
