import logging
from datetime import datetime
from typing import List

from dateutil.tz import tzutc

from investing_algorithm_framework.domain import OrderType, OrderSide, \
    OperationalException, OrderStatus, Order, OrderExecutor, random_number
from investing_algorithm_framework.services.repository_service \
    import RepositoryService

logger = logging.getLogger("investing_algorithm_framework")


class OrderService(RepositoryService):
    """
    Service to manage orders. This service will use the provided
    order executors to execute the orders. The order service is
    responsible for creating, updating, canceling and deleting orders.

    Attributes:
        configuration_service (ConfigurationService): The service
            responsible for managing configurations.
        order_repository (OrderRepository): The repository
            responsible for managing orders.
        position_service (PositionService): The service
            responsible for managing positions.
        portfolio_repository (PortfolioRepository): The repository
            responsible for managing portfolios.
        portfolio_configuration_service (PortfolioConfigurationService):
            service responsible for managing portfolio configurations.
        portfolio_snapshot_service (PortfolioSnapshotService):
            service responsible for managing portfolio snapshots.
        market_credential_service (MarketCredentialService):
            service responsible for managing market credentials.
        trade_service (TradeService): The service responsible for
            managing trades.
    """

    def __init__(
        self,
        configuration_service,
        order_repository,
        position_service,
        portfolio_repository,
        portfolio_configuration_service,
        portfolio_snapshot_service,
        market_credential_service,
        trade_service,
        order_executor_lookup,
        portfolio_provider_lookup
    ):
        super(OrderService, self).__init__(order_repository)
        self.configuration_service = configuration_service
        self.order_repository = order_repository
        self.position_service = position_service
        self.portfolio_repository = portfolio_repository
        self.portfolio_configuration_service = portfolio_configuration_service
        self.portfolio_snapshot_service = portfolio_snapshot_service
        self.market_credential_service = market_credential_service
        self.trade_service = trade_service
        self._order_executors = None
        self._order_executor_lookup = order_executor_lookup
        self._portfolio_provider_lookup = portfolio_provider_lookup

    @property
    def order_executors(self) -> List[OrderExecutor]:
        """
        Returns the order executors for the order service.
        """
        return self._order_executors

    @order_executors.setter
    def order_executors(self, value) -> None:
        """
        Sets the order executors for the order service.
        """
        self._order_executors = value

    def get_order_executor(self, market) -> OrderExecutor:
        """
        Returns the order executor for the given market.

        Args:
            market (str): The market for which to get the order executor.

        Returns:
            OrderExecutor: The order executor for the given market.
        """
        return self._order_executor_lookup.get_order_executor(market)

    def create(self, data, execute=True, validate=True, sync=True) -> Order:
        """
        Function to create an order. The function will create the order and
        execute it if execute is set to True. The function will also validate
        the order if validate is set to True. The function will also sync the
        portfolio with the order if sync is set to True.

        The following only applies if the order is a sell order:

        If stop_losses, or take_profits are in the data, we assume that the
        order has been created by a stop loss or take profit. We will then
        create for the order one or more metadata objects with the
        amount and stop loss id or take profit id. These objects can later
        be used to restore the stop loss or take profit to its original state
        if the order is cancelled or rejected.

        If trades are in the data, we assume that the order has
        been created by a closing a specific trade. We will then create for
        the order one metadata object with the amount and trade id. This
        objects can later be used to restore the trade to its original
        state if the order is cancelled or rejected.

        If there are no trades in the data, we rely on the trade service to
        create the metadata objects for the order.

        The metadata objects are needed because for trades, stop losses and
        take profits we need to know how much of the order has been
        filled at any given time. If the order is cancelled or rejected we
        need to add the pending amount back to the trade, stop loss or take
        profit.

        Args:
            data: dict - the data to create the order with. Data should have
                the following format:
                {
                    "target_symbol": str,
                    "trading_symbol": str,
                    "order_side": str,
                    "order_type": str,
                    "amount": float,
                    "filled" (optional): float, // If set, trades
                        and positions are synced
                    "remaining" (optional): float, // Same as filled
                    "price": float,
                    "portfolio_id": int
                    "stop_losses" (optional): list[dict] - list of stop
                      losses with the following format:
                        {
                            "stop_loss_id": float,
                            "amount": float
                        }
                    "take_profits" (optional): list[dict] - list of
                        take profits with the following format:
                        {
                            "take_profit_id": float,
                            "amount": float
                        }
                    "trades" (optional): list[dict] - list of trades
                        with the following format:
                        {
                            "trade_id": int,
                            "amount": float
                        }
                }

            execute: bool - if True the order will be executed
            validate: bool - if True the order will be validated
            sync: bool - if True the portfolio will be synced with the order

        Returns:
            Order: Order object
        """
        portfolio_id = data["portfolio_id"]
        portfolio = self.portfolio_repository.get(portfolio_id)
        trades = data.get("trades", [])
        stop_losses = data.get("stop_losses", [])
        take_profits = data.get("take_profits", [])

        if "filled" in data:
            del data["filled"]

        if "remaining" in data:
            del data["remaining"]

        if "trades" in data:
            del data["trades"]

        if "stop_losses" in data:
            del data["stop_losses"]

        if "take_profits" in data:
            del data["take_profits"]

        if validate:
            self.validate_order(data, portfolio)

        del data["portfolio_id"]
        symbol = data["target_symbol"]
        data["id"] = self._create_order_id()

        order = self.repository.create(data, save=False)

        if validate:
            self.validate_order(data, portfolio)

        if execute:
            order = self.execute_order(order, portfolio)

        position = self._create_position_if_not_exists(symbol, portfolio)
        order.position_id = position.id
        order = self.order_repository.save(order)
        order_id = order.id
        created_at = order.created_at
        order_side = order.order_side

        if OrderSide.SELL.equals(order_side):
            # Create order metadata if there is a key in the data
            # for trades, stop_losses or take_profits
            self.trade_service.create_order_metadata_with_trade_context(
                sell_order=order,
                trades=trades,
                stop_losses=stop_losses,
                take_profits=take_profits
            )
        else:
            self.trade_service.create_trade_from_buy_order(order)

        if sync:
            order = self.get(order_id)
            if OrderSide.BUY.equals(order_side):
                self._sync_portfolio_with_created_buy_order(order)
            else:
                self._sync_portfolio_with_created_sell_order(order)

        self.create_snapshot(portfolio.id, created_at=created_at)
        order = self.get(order_id)
        return order

    def update(self, object_id, data):
        """
        Function to update an order. The function will update the order and
        sync the portfolio, position and trades if the order has been filled.

        If the order has been cancelled, expired or rejected the function will
        sync the portfolio, position, trades, stop losses, and
        take profits with the order.

        Args:
            object_id: int - the id of the order to update
            data: dict - the data to update the order with
              the following format:
                {
                    "amount": float,
                    "filled" (optional): float,
                    "remaining" (optional): float,
                    "status" (optional): str,
                }

        Returns:
            Order: Order object that has been updated
        """
        previous_order = self.order_repository.get(object_id)
        position = self.position_service.get(previous_order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        new_order = self.order_repository.update(object_id, data)
        filled_difference = new_order.get_filled() \
            - previous_order.get_filled()

        if filled_difference > 0:
            if OrderSide.BUY.equals(new_order.get_order_side()):
                self._sync_with_buy_order_filled(previous_order, new_order)
            else:
                self._sync_with_sell_order_filled(previous_order, new_order)

        if "status" in data:

            if OrderStatus.CANCELED.equals(new_order.get_status()):
                if OrderSide.BUY.equals(new_order.get_order_side()):
                    self._sync_with_buy_order_cancelled(new_order)
                else:
                    self._sync_with_sell_order_cancelled(new_order)

            if OrderStatus.EXPIRED.equals(new_order.get_status()):

                if OrderSide.BUY.equals(new_order.get_order_side()):
                    self._sync_with_buy_order_expired(new_order)
                else:
                    self._sync_with_sell_order_expired(new_order)

            if OrderStatus.REJECTED.equals(new_order.get_status()):

                if OrderSide.BUY.equals(new_order.get_order_side()):
                    self._sync_with_buy_order_rejected(new_order)
                else:
                    self._sync_with_sell_order_expired(new_order)

        if "updated_at" in data:
            created_at = data["updated_at"]
        else:
            created_at = datetime.now(tz=tzutc())

        self.create_snapshot(portfolio.id, created_at=created_at)
        return new_order

    def execute_order(self, order, portfolio) -> Order:
        """
        Function to execute an order. The function will execute the order
        with a matching order executor. The function will also update
        the order attributes with the external order attributes.

        Args:
            order: Order object representing the order to be executed
            portfolio: Portfolio object representing the portfolio in which

        Returns:
            order: Order object representing the executed order
        """
        logger.info(
            f"Executing order {order.get_symbol()} with "
            f"amount {order.get_amount()} "
            f"and price {order.get_price()}"
        )

        order_executor = self.get_order_executor(portfolio.market)
        market_credential = self.market_credential_service.get(
            portfolio.market
        )
        external_order = order_executor.execute_order(
            portfolio, order, market_credential
        )
        logger.info(f"Executed order: {external_order.to_dict()}")
        order.set_external_id(external_order.get_external_id())
        order.set_status(external_order.get_status())
        order.set_filled(external_order.get_filled())
        order.set_remaining(external_order.get_remaining())
        order.updated_at = datetime.now(tz=tzutc())
        return order

    def validate_order(self, order_data, portfolio):

        if OrderSide.BUY.equals(order_data["order_side"]):
            self.validate_buy_order(order_data, portfolio)
        else:
            self.validate_sell_order(order_data, portfolio)

        if OrderType.LIMIT.equals(order_data["order_type"]):
            self.validate_limit_order(order_data, portfolio)
        else:
            raise OperationalException(
                f"Order type {order_data['order_type']} is not supported"
            )

    def validate_sell_order(self, order_data, portfolio):

        if not self.position_service.exists(
            {
                "symbol": order_data["target_symbol"],
                "portfolio": portfolio.id
            }
        ):
            raise OperationalException(
                "Can't add sell order to non existing position"
            )

        position = self.position_service\
            .find(
                {
                    "symbol": order_data["target_symbol"],
                    "portfolio": portfolio.id
                }
            )

        if position.get_amount() < order_data["amount"]:
            raise OperationalException(
                f"Order amount {order_data['amount']} is larger " +
                f"then amount of open position {position.get_amount()}"
            )

        if not order_data["trading_symbol"] == portfolio.trading_symbol:
            raise OperationalException(
                f"Can't add sell order with target "
                f"symbol {order_data['target_symbol']} to "
                f"portfolio with trading symbol {portfolio.trading_symbol}"
            )

    @staticmethod
    def validate_buy_order(order_data, portfolio):

        if not order_data["trading_symbol"] == portfolio.trading_symbol:
            raise OperationalException(
                f"Can't add buy order with trading "
                f"symbol {order_data['trading_symbol']} to "
                f"portfolio with trading symbol {portfolio.trading_symbol}"
            )

    def validate_limit_order(self, order_data, portfolio):

        if OrderSide.SELL.equals(order_data["order_side"]):
            amount = order_data["amount"]
            position = self.position_service\
                .find(
                    {
                        "portfolio": portfolio.id,
                        "symbol": order_data["target_symbol"]
                    }
                )

            if amount <= 0:
                raise OperationalException(
                    f"Order amount: {amount} {position.symbol}, is "
                    f"less or equal to 0"
                )

            if amount > position.get_amount():
                raise OperationalException(
                    f"Order amount: {amount} {position.symbol}, is "
                    f"larger then position size: {position.get_amount()} "
                    f"{position.symbol} of the portfolio"
                )
        else:
            total_price = order_data["amount"] * order_data["price"]
            unallocated_position = self.position_service\
                .find(
                    {
                        "portfolio": portfolio.id,
                        "symbol": portfolio.trading_symbol
                    }
                )
            unallocated_amount = unallocated_position.get_amount()

            if unallocated_amount is None:
                raise OperationalException(
                    "Unallocated amount of the portfolio is None" +
                    "can't validate limit order. Please check if " +
                    "the portfolio configuration is correct"
                )

            if unallocated_amount < total_price:
                raise OperationalException(
                    f"Order total: {total_price} "
                    f"{portfolio.trading_symbol}, is "
                    f"larger then unallocated size: {portfolio.unallocated} "
                    f"{portfolio.trading_symbol} of the portfolio"
                )

    def check_pending_orders(self, portfolio=None):
        """
        Function to check if
        """
        if portfolio is not None:
            pending_orders = self.get_all(
                {
                    "status": OrderStatus.OPEN.value,
                    "portfolio_id": portfolio.id
                }
            )
        else:
            pending_orders = self.get_all({"status": OrderStatus.OPEN.value})

        for order in pending_orders:
            position = self.position_service.get(order.position_id)
            portfolio = self.portfolio_repository.get(position.portfolio_id)
            portfolio_provider = self._portfolio_provider_lookup\
                .get_portfolio_provider(portfolio.market)
            market_credential = self.market_credential_service.get(
                portfolio.market
            )
            logger.info(
                f"Checking {order.get_order_side()} order {order.get_id()} "
                f"with external id: {order.get_external_id()} "
                f"at market {portfolio.market}"
            )
            external_order = portfolio_provider.get_order(
                portfolio, order, market_credential
            )
            self.update(order.id, external_order.to_dict())

    def _create_position_if_not_exists(self, symbol, portfolio):
        if not self.position_service.exists(
            {"portfolio": portfolio.id, "symbol": symbol}
        ):
            self.position_service \
                .create({"portfolio_id": portfolio.id, "symbol": symbol})
            position = self.position_service \
                .find({"portfolio": portfolio.id, "symbol": symbol})
        else:
            position = self.position_service \
                .find({"portfolio": portfolio.id, "symbol": symbol})

        return position

    def _sync_portfolio_with_created_buy_order(self, order):
        """
        Function to sync the portfolio and positions with a created buy order.

        Args:
            order: the order object representing the buy order

        Returns:
            None
        """
        self.position_service.update_positions_with_created_buy_order(
            order
        )
        position = self.position_service.get(order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        size = order.get_size()
        self.portfolio_repository.update(
            portfolio.id, {"unallocated": portfolio.get_unallocated() - size}
        )

    def _sync_portfolio_with_created_sell_order(self, order):
        """
        Function to sync the portfolio with a created sell order. The
        function will subtract the amount of the order from the position and
        the trade amount. If the sell order is already filled, then
        the function will also update the portfolio and the
        trading symbol position.

        The portfolio will not be updated because the sell order has not been
        filled.

        Args:
            order: Order object representing the sell order

        Returns:
            None
        """
        self.position_service.update_positions_with_created_sell_order(
            order
        )

        filled = order.get_filled()

        if filled > 0:
            position = self.position_service.get(order.position_id)
            portfolio = self.portfolio_repository.get(position.portfolio_id)
            size = filled * order.get_price()
            self.portfolio_repository.update(
                portfolio.id,
                {
                    "unallocated": portfolio.get_unallocated() + size
                }
            )

    def cancel_order(self, order):
        self.check_pending_orders()
        order = self.order_repository.get(order.id)

        if order is not None:

            if OrderStatus.OPEN.equals(order.status):
                portfolio = self.portfolio_repository\
                    .find({"position": order.position_id})
                market_credential = self.market_credential_service.get(
                    portfolio.market
                )
                order_executor = self.get_order_executor(portfolio.market)
                order = order_executor\
                    .cancel_order(portfolio, order, market_credential)
                self.update(order.id, order.to_dict())

    def _sync_with_buy_order_filled(self, previous_order, current_order):
        """
        Function to sync the portfolio, position and trades with the
        filled buy order.

        Args:
            previous_order: the previous order object
            current_order:  the current order object

        Returns:
            None
        """
        logger.info("Syncing portfolio with filled buy order")
        filled_difference = current_order.get_filled() - \
            previous_order.get_filled()
        filled_size = filled_difference * current_order.get_price()

        if filled_difference <= 0:
            return

        self.position_service.update_positions_with_buy_order_filled(
            current_order, filled_difference
        )
        position = self.position_service.get(current_order.position_id)

        # Update portfolio
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        self.portfolio_repository.update(
            portfolio.id,
            {
                "total_cost": portfolio.get_total_cost() + filled_size,
                "total_trade_volume": portfolio.get_total_trade_volume()
                + filled_size,
            }
        )

        self.trade_service.update_trade_with_buy_order(
            filled_difference, current_order
        )

    def _sync_with_sell_order_filled(self, previous_order, current_order):
        """
        Function to sync the portfolio, position and trades with the
        filled sell order. The function will update the portfolio and
        position with the filled amount of the order. The function will
        also update the trades with the filled amount of the order.

        Args:
            previous_order: Order object representing the previous order
            current_order: Order object representing the current order

        Returns:
            None
        """
        filled_difference = current_order.get_filled() - \
            previous_order.get_filled()
        filled_size = filled_difference * current_order.get_price()

        if filled_difference <= 0:
            return

        logger.info(
            f"Syncing portfolio with filled sell "
            f"order {current_order.get_id()} with filled amount "
            f"{filled_difference}"
        )

        # Get position
        position = self.position_service.get(current_order.position_id)

        # Update the portfolio
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        self.portfolio_repository.update(
            portfolio.id,
            {
                "unallocated": portfolio.get_unallocated() + filled_size,
                "total_trade_volume": portfolio.get_total_trade_volume()
                + filled_size,
            }
        )

        # Update the trading symbol position
        trading_symbol_position = self.position_service.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_service.update(
            trading_symbol_position.id,
            {
                "amount":
                    trading_symbol_position.get_amount() + filled_size
            }
        )

        # Update the position if the amount has changed
        if current_order.amount != previous_order.amount:
            difference = current_order.amount - previous_order.amount
            cost = difference * current_order.get_price()
            self.position_service.update(
                position.id,
                {
                    "amount": position.get_amount() - difference,
                    "cost": position.get_cost() - cost
                }
            )

        self.trade_service.update_trade_with_filled_sell_order(
            filled_difference, current_order
        )

    def _sync_with_buy_order_cancelled(self, order):
        remaining = order.get_amount() - order.get_filled()
        size = remaining * order.get_price()

        # Add the remaining amount to the portfolio
        portfolio = self.portfolio_repository.find(
            {
                "position": order.position_id
            }
        )
        self.portfolio_repository.update(
            portfolio.id,
            {
                "unallocated": portfolio.get_unallocated() + size
            }
        )

        # Add the remaining amount to the trading symbol position
        trading_symbol_position = self.position_service.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_service.update(
            trading_symbol_position.id,
            {
                "amount": trading_symbol_position.get_amount() + remaining
            }
        )

    def _sync_with_sell_order_cancelled(self, order):
        remaining = order.get_amount() - order.get_filled()

        # Add the remaining back to the position
        position = self.position_service.get(order.position_id)
        self.position_service.update(
            position.id,
            {
                "amount": position.get_amount() + remaining
            }
        )
        self.trade_service.update_trade_with_removed_sell_order(order)

    def _sync_with_buy_order_failed(self, order):
        remaining = order.get_amount() - order.get_filled()
        size = remaining * order.get_price()

        # Add the remaining amount to the portfolio
        portfolio = self.portfolio_repository.find(
            {
                "position": order.position_id
            }
        )
        self.portfolio_repository.update(
            portfolio.id,
            {
                "unallocated": portfolio.get_unallocated() + size
            }
        )

        # Add the remaining amount to the trading symbol position
        trading_symbol_position = self.position_service.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_service.update(
            trading_symbol_position.id,
            {
                "amount": trading_symbol_position.get_amount() + remaining
            }
        )

    def _sync_with_sell_order_failed(self, order):
        remaining = order.get_amount() - order.get_filled()

        # Add the remaining back to the position
        position = self.position_service.get(order.position_id)
        self.position_service.update(
            position.id,
            {
                "amount": position.get_amount() + remaining
            }
        )

        self.trade_service.update_trade_with_removed_sell_order(order)

    def _sync_with_buy_order_expired(self, order):
        remaining = order.get_amount() - order.get_filled()
        size = remaining * order.get_price()

        # Add the remaining amount to the portfolio
        portfolio = self.portfolio_repository.find(
            {
                "position": order.position_id
            }
        )
        self.portfolio_repository.update(
            portfolio.id,
            {
                "unallocated": portfolio.get_unallocated() + size
            }
        )

        # Add the remaining amount to the trading symbol position
        trading_symbol_position = self.position_service.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_service.update(
            trading_symbol_position.id,
            {
                "amount": trading_symbol_position.get_amount() + remaining
            }
        )

    def _sync_with_sell_order_expired(self, order):
        remaining = order.get_amount() - order.get_filled()

        # Add the remaining back to the position
        position = self.position_service.get(order.position_id)
        self.position_service.update(
            position.id,
            {
                "amount": position.get_amount() + remaining
            }
        )

        self.trade_service.update_trade_with_removed_sell_order(order)

    def _sync_with_buy_order_rejected(self, order):
        remaining = order.get_amount() - order.get_filled()
        size = remaining * order.get_price()

        # Add the remaining amount to the portfolio
        portfolio = self.portfolio_repository.find(
            {
                "position": order.position_id
            }
        )
        self.portfolio_repository.update(
            portfolio.id,
            {
                "unallocated": portfolio.get_unallocated() + size
            }
        )

        # Add the remaining amount to the trading symbol position
        trading_symbol_position = self.position_service.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_service.update(
            trading_symbol_position.id,
            {
                "amount": trading_symbol_position.get_amount() + remaining
            }
        )

    def _sync_with_sell_order_rejected(self, order):
        remaining = order.get_amount() - order.get_filled()

        # Add the remaining back to the position
        position = self.position_service.get(order.position_id)
        self.position_service.update(
            position.id,
            {
                "amount": position.get_amount() + remaining
            }
        )

        self.trade_service.update_trade_with_removed_sell_order(order)

    def create_snapshot(self, portfolio_id, created_at=None):

        if created_at is None:
            created_at = datetime.now(tz=tzutc())

        portfolio = self.portfolio_repository.get(portfolio_id)
        pending_orders = self.get_all(
            {
                "order_side": OrderSide.BUY.value,
                "status": OrderStatus.OPEN.value,
                "portfolio_id": portfolio.id
            }
        )
        created_orders = self.get_all(
            {
                "order_side": OrderSide.BUY.value,
                "status": OrderStatus.CREATED.value,
                "portfolio_id": portfolio.id
            }
        )
        return self.portfolio_snapshot_service.create_snapshot(
            portfolio,
            pending_orders=pending_orders,
            created_orders=created_orders,
            created_at=created_at
        )

    def _create_order_id(self):
        """
        Function to create a new order id. The function will
        create a new order id and return it.

        Returns:
            int: The new order id
        """

        unique = False
        order_id = None

        while not unique:
            order_id = random_number(12)

            if not self.repository.exists({"id": order_id}):
                unique = True

        return order_id
