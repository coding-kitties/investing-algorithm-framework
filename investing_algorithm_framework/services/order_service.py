import logging
from queue import PriorityQueue
from datetime import datetime

from investing_algorithm_framework.domain import OrderType, OrderSide, \
    OperationalException, OrderStatus, parse_string_to_decimal, \
    parse_decimal_to_string
from investing_algorithm_framework.services.repository_service \
    import RepositoryService

logger = logging.getLogger("investing_algorithm_framework")


class OrderService(RepositoryService):

    def __init__(
        self,
        order_repository,
        order_fee_repository,
        market_service,
        position_repository,
        portfolio_repository,
        portfolio_configuration_service,
    ):
        super(OrderService, self).__init__(order_repository)
        self.order_repository = order_repository
        self.order_fee_repository = order_fee_repository
        self.market_service = market_service
        self.position_repository = position_repository
        self.portfolio_repository = portfolio_repository
        self.portfolio_configuration_service = portfolio_configuration_service

    def create(self, data, execute=True, validate=True, sync=True):
        portfolio_id = data["portfolio_id"]
        portfolio = self.portfolio_repository.get(portfolio_id)

        if validate:
            self.validate_order(data, portfolio)

        order_fee = None

        if "fee" in data:
            order_fee = data.pop("fee")

        del data["portfolio_id"]
        symbol = data["target_symbol"]

        if validate:
            self.validate_order(data, portfolio)

        position = self._create_position_if_not_exists(symbol, portfolio)
        data["position_id"] = position.id
        data["remaining_amount"] = data["amount"]
        data["status"] = OrderStatus.OPEN.value
        order = self.order_repository.create(data)
        order_id = order.id

        if order_fee:
            order_fee["order_id"] = order_id
            self.order_fee_repository.create(order_fee)

        if execute:
            portfolio.configuration = self.portfolio_configuration_service\
                .get(portfolio.identifier)
            self.execute_order(order_id, portfolio)

        if sync:
            if OrderSide.BUY.equals(order.get_side()):
                self._sync_portfolio_with_created_buy_order(order)
            else:
                self._sync_portfolio_with_created_sell_order(order)

        return order

    def update(self, object_id, data):
        previous_order = self.order_repository.get(object_id)

        if "fee" in data:
            order_fee_data = data.pop("fee")

            if order_fee_data is not None:
                if self.order_fee_repository.exists({"order_id": object_id}):
                    order_fee = self.order_fee_repository\
                        .find({"order_id": object_id})
                    self.order_fee_repository\
                        .update(order_fee.id, order_fee_data)
                else:
                    order_fee_data["order_id"] = object_id
                    self.order_fee_repository.create(order_fee_data)

        new_order = self.order_repository.update(object_id, data)
        filled_difference = new_order.get_filled() - previous_order.get_filled()

        if filled_difference:

            if OrderSide.BUY.equals(new_order.get_side()):
                self._sync_with_buy_order_filled(previous_order, new_order)
            else:
                self._sync_with_sell_order_filled(previous_order, new_order)

        if "status" in data:

            if OrderStatus.CANCELED.equals(new_order.get_status()):

                if OrderSide.BUY.equals(new_order.get_side()):
                    self._sync_with_buy_order_cancelled(new_order)
                else:
                    self._sync_with_sell_order_cancelled(new_order)

            if OrderStatus.EXPIRED.equals(new_order.get_status()):

                if OrderSide.BUY.equals(new_order.get_side()):
                    self._sync_with_buy_order_expired(new_order)
                else:
                    self._sync_with_sell_order_expired(new_order)

            if OrderStatus.REJECTED.equals(new_order.get_status()):

                if OrderSide.BUY.equals(new_order.get_side()):
                    self._sync_with_buy_order_rejected(new_order)
                else:
                    self._sync_with_sell_order_expired(new_order)

        return new_order

    def get_order_fee(self, order_id):
        return self.order_fee_repository.find({"order": order_id})

    def execute_order(self, order_id, portfolio):
        self.market_service.initialize(portfolio.configuration)
        order = self.get(order_id)

        try:
            if OrderType.LIMIT.equals(order.get_order_type()):

                if OrderSide.BUY.equals(order.get_side()):
                    executed_order = self.market_service.create_limit_buy_order(
                        target_symbol=order.get_target_symbol(),
                        trading_symbol=order.get_trading_symbol(),
                        amount=parse_decimal_to_string(order.get_amount()),
                        price=parse_decimal_to_string(order.get_price())
                    )
                else:
                    executed_order = self.market_service.create_limit_sell_order(
                        target_symbol=order.get_target_symbol(),
                        trading_symbol=order.get_trading_symbol(),
                        amount=parse_decimal_to_string(order.get_amount()),
                        price=parse_decimal_to_string(order.get_price())
                    )
            else:
                if OrderSide.BUY.equals(order.get_side()):
                    raise OperationalException("Market buy order not supported")
                else:
                    executed_order = self.market_service.create_market_sell_order(
                        target_symbol=order.get_target_symbol(),
                        trading_symbol=order.get_trading_symbol(),
                        amount=parse_decimal_to_string(order.get_amount()),
                    )

            self.update(order_id, executed_order.to_dict())
        except Exception as e:
            logger.error("Error executing order: {}".format(e))
            self.update(order_id, {"status": OrderStatus.REJECTED.value})
            raise e

    def validate_order(self, order_data, portfolio):

        if OrderSide.BUY.equals(order_data["side"]):
            self.validate_buy_order(order_data, portfolio)
        else:
            self.validate_sell_order(order_data, portfolio)

        if OrderType.LIMIT.equals(order_data["order_type"]):
            self.validate_limit_order(order_data, portfolio)
        else:
            self.validate_market_order(order_data, portfolio)

    def validate_sell_order(self, order_data, portfolio):
        if not self.position_repository.exists(
            {
                "symbol": order_data["target_symbol"],
                "portfolio": portfolio.id
            }
        ):
            raise OperationalException(
                "Can't add sell order to non existing position"
            )

        position = self.position_repository\
            .find(
                {
                    "symbol": order_data["target_symbol"],
                    "portfolio": portfolio.id
                }
            )

        if position.get_amount() < parse_string_to_decimal(order_data["amount"]):
            raise OperationalException(
                "Order amount is larger then amount of open position"
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

        if OrderSide.SELL.equals(order_data["side"]):
            amount = parse_string_to_decimal(order_data["amount"])
            position = self.position_repository\
                .find(
                    {
                        "portfolio": portfolio.id,
                        "symbol": order_data["target_symbol"]
                    }
                )
            if amount > position.get_amount():
                raise OperationalException(
                    f"Order amount: {amount} {position.symbol}, is "
                    f"larger then position size: {position.get_amount()} "
                    f"{position.symbol} of the portfolio"
                )
        else:
            total_price = parse_string_to_decimal(order_data["amount"]) \
                          * parse_string_to_decimal(order_data["price"])
            unallocated_position = self.position_repository\
                .find(
                    {
                        "portfolio": portfolio.id,
                        "symbol": portfolio.trading_symbol
                    }
                )
            amount = unallocated_position.get_amount()

            if amount < total_price:
                raise OperationalException(
                    f"Order total: {total_price} {portfolio.trading_symbol}, is "
                    f"larger then unallocated size: {portfolio.unallocated} "
                    f"{portfolio.trading_symbol} of the portfolio"
                )

    def validate_market_order(self, order_data, portfolio):

        if OrderSide.BUY.equals(order_data["side"]):

            if "amount" not in order_data:
                raise OperationalException(
                    f"Market order needs an amount specified in the trading "
                    f"symbol {order_data['trading_symbol']}"
                )

            if order_data['amount'] > portfolio.unallocated:
                raise OperationalException(
                    f"Market order amount "
                    f"{order_data['amount']}"
                    f"{portfolio.trading_symbol.upper()} is larger then "
                    f"unallocated {portfolio.unallocated} "
                    f"{portfolio.trading_symbol.upper()}"
                )
        else:
            position = self.position_repository\
                .find(
                    {
                        "symbol": order_data["target_symbol"],
                        "portfolio": portfolio.id
                    }
                )

            if position is None:
                raise OperationalException(
                    "Can't add market sell order to non existing position"
                )

            if parse_string_to_decimal(order_data['amount']) > position.get_amount():
                raise OperationalException(
                    "Sell order amount larger then position size"
                )

    def check_pending_orders(self):
        pending_orders = self.get_all({"status": OrderStatus.OPEN.value})
        logger.info(f"Checking {len(pending_orders)} open orders")

        for order in pending_orders:
            position = self.position_repository.get(order.position_id)
            portfolio = self.portfolio_repository.get(position.portfolio_id)
            portfolio_configuration = self.portfolio_configuration_service\
                .get(portfolio.identifier)
            self.market_service.initialize(portfolio_configuration)
            external_order = self.market_service.get_order(order)
            self.update(order.id, external_order.to_dict())

    def _create_position_if_not_exists(self, symbol, portfolio):
        if not self.position_repository.exists(
            {"portfolio": portfolio.id, "symbol": symbol}
        ):
            self.position_repository \
                .create({"portfolio_id": portfolio.id, "symbol": symbol})
            position = self.position_repository \
                .find({"portfolio": portfolio.id, "symbol": symbol})
        else:
            position = self.position_repository \
                .find({"portfolio": portfolio.id, "symbol": symbol})

        return position

    def _sync_portfolio_with_created_buy_order(self, order):
        position = self.position_repository.get(order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        size = order.get_amount() * order.get_price()
        trading_symbol_position = self.position_repository.find(
            {
                "portfolio": portfolio.id,
                "symbol": portfolio.trading_symbol
            }
        )
        self.portfolio_repository.update(
            portfolio.id, {"unallocated": portfolio.get_unallocated() - size}
        )
        self.position_repository.update(
            trading_symbol_position.id,
            {
                "amount": trading_symbol_position.get_amount() - size
            }
        )

    def _sync_portfolio_with_created_sell_order(self, order):
        position = self.position_repository.get(order.position_id)
        self.position_repository.update(
            position.id,
            {
                "amount": position.get_amount() - order.get_amount()
            }
        )

    def cancel_order(self, order_id):
        self.check_pending_orders()
        order = self.order_repository.get(order_id)

        if order is not None:

            if OrderStatus.OPEN.equals(order.status):
                portfolio = self.portfolio_repository\
                    .find({"position": order.position_id})
                portfolio_configuration = self.portfolio_configuration_service\
                    .get(portfolio.identifier)
                self.market_service.initialize(portfolio_configuration)
                self.market_service.cancel_order(order_id)

    def _sync_with_buy_order_filled(self, previous_order, current_order):
        filled_difference = current_order.get_filled() - \
                            previous_order.get_filled()
        filled_size = filled_difference * current_order.get_price()

        if filled_difference <= 0:
            return

        # Update position
        position = self.position_repository.get(current_order.position_id)
        self.position_repository.update(
            position.id,
            {
                "amount": position.get_amount() + filled_difference,
                "cost": position.get_cost() + filled_size,
            }
        )

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

    def _sync_with_sell_order_filled(self, previous_order, current_order):
        filled_difference = current_order.get_filled() - \
                            previous_order.get_filled()
        filled_size = filled_difference * current_order.get_price()

        if filled_difference <= 0:
            return

        # Get position
        position = self.position_repository.get(current_order.position_id)

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
        trading_symbol_position = self.position_repository.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_repository.update(
            trading_symbol_position.id,
            {
                "amount": trading_symbol_position.get_amount()
                + filled_size
            }
        )

        self._close_trades(filled_difference, current_order)

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
        trading_symbol_position = self.position_repository.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_repository.update(
            trading_symbol_position.id,
            {
                "amount": trading_symbol_position.get_amount() + remaining
            }
        )

    def _sync_with_sell_order_cancelled(self, order):
        remaining = order.get_amount() - order.get_filled()

        # Add the remaining back to the position
        position = self.position_repository.get(order.position_id)
        self.position_repository.update(
            position.id,
            {
                "amount": position.get_amount() + remaining
            }
        )

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
        trading_symbol_position = self.position_repository.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_repository.update(
            trading_symbol_position.id,
            {
                "amount": trading_symbol_position.get_amount() + remaining
            }
        )

    def _sync_with_sell_order_failed(self, order):
        remaining = order.get_amount() - order.get_filled()

        # Add the remaining back to the position
        position = self.position_repository.get(order.position_id)
        self.position_repository.update(
            position.id,
            {
                "amount": position.get_amount() + remaining
            }
        )

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
        trading_symbol_position = self.position_repository.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_repository.update(
            trading_symbol_position.id,
            {
                "amount": trading_symbol_position.get_amount() + remaining
            }
        )

    def _sync_with_sell_order_expired(self, order):
        remaining = order.get_amount() - order.get_filled()

        # Add the remaining back to the position
        position = self.position_repository.get(order.position_id)
        self.position_repository.update(
            position.id,
            {
                "amount": position.get_amount() + remaining
            }
        )

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
        trading_symbol_position = self.position_repository.find(
            {
                "symbol": portfolio.trading_symbol,
                "portfolio": portfolio.id
            }
        )
        self.position_repository.update(
            trading_symbol_position.id,
            {
                "amount": trading_symbol_position.get_amount() + remaining
            }
        )

    def _sync_with_sell_order_rejected(self, order):
        remaining = order.get_amount() - order.get_filled()

        # Add the remaining back to the position
        position = self.position_repository.get(order.position_id)
        self.position_repository.update(
            position.id,
            {
                "amount": position.get_amount() + remaining
            }
        )

    def _close_trades(self, amount_to_close, sell_order):
        matching_buy_orders = self.order_repository.get_all(
            {
                "position": sell_order.position_id,
                "order_side": "buy",
                "trade_closed_at": None
            }
        )
        order_queue = PriorityQueue()

        for order in matching_buy_orders:
            order_queue.put(order)

        total_net_gain = 0
        total_cost = 0

        while amount_to_close > 0 and not order_queue.empty():
            buy_order = order_queue.get()

            if buy_order.get_trade_closed_amount() != None:
                available_to_close = buy_order.get_filled() \
                                     - buy_order.get_trade_closed_amount()
            else:
                available_to_close = buy_order.get_filled()

            if amount_to_close >= available_to_close:
                to_be_closed = available_to_close
                remaining = amount_to_close - to_be_closed
                cost = buy_order.get_price() * to_be_closed
                net_gain = (sell_order.get_price() - buy_order.get_price()) * to_be_closed
                amount_to_close = remaining
                self.order_repository.update(
                    buy_order.id,
                    {
                        "trade_closed_amount": buy_order.get_filled(),
                        "trade_closed_at": datetime.utcnow(),
                        "trade_closed_price": sell_order.get_price(),
                        "net_gain": buy_order.get_net_gain() + net_gain
                    }
                )
            else:
                to_be_closed = amount_to_close
                net_gain = (sell_order.get_price() - buy_order.get_price()) * to_be_closed
                cost = buy_order.get_price() * amount_to_close
                self.order_repository.update(
                    buy_order.id,
                    {
                        "trade_closed_amount": buy_order.get_trade_closed_amount() + to_be_closed,
                        "trade_closed_price": sell_order.get_price(),
                        "net_gain": buy_order.get_net_gain() + net_gain
                    }
                )
                amount_to_close = 0

            total_net_gain += net_gain
            total_cost += cost

        position = self.position_repository.get(sell_order.position_id)

        # Update portfolio
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        self.portfolio_repository.update(
            portfolio.id,
            {
                "total_net_gain": portfolio.get_total_net_gain() + total_net_gain,
                "total_cost": portfolio.get_total_cost() - total_cost
            }
        )
        # Update the position
        position = self.position_repository.get(sell_order.position_id)
        self.position_repository.update(
            position.id,
            {
                "cost": position.get_cost() - total_cost
            }
        )

        # Update the sell order
        self.order_repository.update(
            sell_order.id,
            {
                "trade_closed_amount": sell_order.get_filled(),
                "trade_closed_at": datetime.utcnow(),
                "trade_closed_price": sell_order.get_price(),
                "net_gain": sell_order.get_net_gain() + total_net_gain
            }
        )
