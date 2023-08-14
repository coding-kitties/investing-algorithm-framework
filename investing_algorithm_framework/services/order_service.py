import logging
from datetime import datetime

from investing_algorithm_framework.domain import OrderType, OrderSide, \
    OperationalException, OrderStatus
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
        position_cost_repository,
        portfolio_repository,
        portfolio_configuration_service,
    ):
        super(OrderService, self).__init__(order_repository)
        self.order_repository = order_repository
        self.order_fee_repository = order_fee_repository
        self.market_service = market_service
        self.position_repository = position_repository
        self.position_cost_repository = position_cost_repository
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

        if "fee" in data:
            order_fee_data = data.pop("fee")

            if self.order_fee_repository.exists({"order_id": object_id}):
                order_fee = self.order_fee_repository.find({"order_id": object_id})
                self.order_fee_repository.update(order_fee.id, order_fee_data)
            else:
                order_fee_data["order_id"] = object_id
                self.order_fee_repository.create(order_fee_data)

        return self.order_repository.update(object_id, data)

    def get_order_fee(self, order_id):
        return self.order_fee_repository.find({"order": order_id})

    def execute_order(self, order_id, portfolio):
        self.market_service.initialize(portfolio.configuration)
        order = self.get(order_id)

        if OrderType.LIMIT.equals(order.get_type()):

            if OrderSide.BUY.equals(order.get_side()):
                self.market_service.create_limit_buy_order(
                    target_symbol=order.get_target_symbol(),
                    trading_symbol=order.get_trading_symbol(),
                    amount=order.get_amount(),
                    price=order.get_price()
                )
            else:
                self.market_service.create_limit_sell_order(
                    target_symbol=order.get_target_symbol(),
                    trading_symbol=order.get_trading_symbol(),
                    amount=order.get_amount(),
                    price=order.get_price()
                )
        else:
            if OrderSide.BUY.equals(order.get_side()):
                raise OperationalException("Market buy order not supported")
            else:
                self.market_service.create_market_sell_order(
                    target_symbol=order.get_target_symbol(),
                    trading_symbol=order.get_trading_symbol(),
                    amount=order.get_amount(),
                )

        self.update(order_id, {"status": OrderStatus.OPEN.value})

    def validate_order(self, order_data, portfolio):

        if OrderSide.BUY.equals(order_data["side"]):
            self.validate_buy_order(order_data, portfolio)
        else:
            self.validate_sell_order(order_data, portfolio)

        if OrderType.LIMIT.equals(order_data["type"]):
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

        if position.amount < order_data["amount"]:
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
            amount = order_data["amount"]
            position = self.position_repository\
                .find(
                    {
                        "portfolio": portfolio.id,
                        "symbol": portfolio.trading_symbol
                    }
                )
            if amount > position.amount:
                raise OperationalException(
                    f"Order amount: {amount} {portfolio.trading_symbol}, is "
                    f"larger then position size: {position.amount} "
                    f"{portfolio.trading_symbol} of the portfolio"
                )
        else:
            total_price = order_data["amount"] * order_data["price"]
            unallocated_position = self.position_repository\
                .find(
                    {
                        "portfolio": portfolio.id,
                        "symbol": portfolio.trading_symbol
                    }
                )
            amount = unallocated_position.amount

            if amount < total_price:
                raise OperationalException(
                    f"Order total: {total_price} {portfolio.trading_symbol}, is "
                    f"larger then unallocated size: {amount} "
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

            if order_data['amount'] > position.amount:
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

            if OrderStatus.from_value(external_order.status)\
                    .equals(order.status):
                continue

            updated_order = self.update(order.id, external_order.to_dict())

            if OrderStatus.CLOSED.equals(updated_order.status):
                logger.info(f"Order {updated_order.id} closed")

                if OrderSide.BUY.equals(updated_order.side):
                    self._sync_portfolio_with_executed_buy_order(updated_order)
                else:
                    self._sync_portfolio_with_executed_sell_order(updated_order)
            elif OrderStatus.CANCELED.equals(updated_order.status):
                logger.info(f"Order {updated_order.id} canceled")

                if OrderSide.BUY.equals(updated_order.side):
                    self._sync_portfolio_with_cancelled_buy_order(
                        updated_order
                    )
                else:
                    self._sync_portfolio_with_cancelled_sell_order(
                        updated_order
                    )
            elif OrderStatus.REJECTED.equals(updated_order.status) \
                    or OrderStatus.EXPIRED.equals(updated_order.status):
                logger.info(f"Order {updated_order.id} rejected or expired")

                if OrderSide.BUY.equals(updated_order.side):
                    self._sync_portfolio_with_failed_buy_order(updated_order)
                else:
                    self._sync_portfolio_with_failed_sell_order(updated_order)

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
        trading_symbol_position = self.position_repository.find(
            {
                "portfolio": portfolio.id,
                "symbol": portfolio.trading_symbol
            }
        )
        self.portfolio_repository.update(
            portfolio.id,
            {"unallocated": portfolio.unallocated - order.amount * order.price}
        )
        self.position_repository.update(
            trading_symbol_position.id,
            {
                "amount": trading_symbol_position.amount - order.amount * order.price
            }
        )

    def _sync_portfolio_with_created_sell_order(self, order):
        position = self.position_repository.get(order.position_id)
        self.position_repository.update(
            position.id,
            {
                "amount": position.amount - order.amount
            }
        )

    def _sync_portfolio_with_executed_buy_order(self, order):
        position = self.position_repository.get(order.position_id)
        position_cost = self.position_cost_repository.create(
            {
                "position_id": position.id,
                "price": order.price,
                "amount": order.amount,
                "created_at": order.created_at,
            }
        )
        self.position_repository.update(
            position.id, {"amount": position.amount + order.amount}
        )
        cost = position_cost.price * position_cost.amount
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        self.portfolio_repository.update(
            portfolio.id,
            {
                "total_cost": portfolio.total_cost + cost,
            }
        )

    def _sync_portfolio_with_executed_sell_order(self, order):
        position = self.position_repository.get(order.position_id)
        portfolio = self.portfolio_repository.get(position.portfolio_id)
        amount_to_sell = order.amount
        net_gain = 0
        revenue = order.amount * order.price
        total_cost = 0

        while amount_to_sell > 0:
            position_cost = self.position_cost_repository.find(
                {"position": position.id}
            )
            if position_cost is None:
                break

            if position_cost.amount > amount_to_sell:
                net_gain += amount_to_sell * \
                            (order.price - position_cost.price)
                self.position_cost_repository.update(
                    position_cost.id,
                    {"amount": position_cost.amount - amount_to_sell}
                )
                amount_to_sell = 0
            else:
                net_gain += position_cost.amount * (order.price - position_cost.price)
                total_cost += position_cost.amount * position_cost.price
                amount_to_sell -= position_cost.amount
                self.position_cost_repository.delete(position_cost.id)

            # Update the buy order net gain
            buy_order = self.order_repository.find(
                {
                    "position": position.id,
                    "side": OrderSide.BUY.value,
                    "created_at": position_cost.created_at
                }
            )

            if buy_order is not None:
                self.order_repository.update(
                    buy_order.id,
                    {
                        "net_gain": buy_order.net_gain + net_gain,
                        "trade_closed_at": datetime.now(),
                        "trade_closing_price": order.price,
                    }
                )

        # Update the portfolio
        self.portfolio_repository.update(
            portfolio.id,
            {
                "unallocated": portfolio.unallocated + revenue,
                "total_net_gain": portfolio.total_net_gain + net_gain,
                "net_size": portfolio.net_size + revenue,
            }
        )

    def _sync_portfolio_with_cancelled_buy_order(self, order):
        position = self.position_repository.find({"id": order.position_id})
        portfolio = self.portfolio_repository.get(position.portfolio_id)

        if OrderType.LIMIT.equals(order.type):
            self.portfolio_repository.update(
                portfolio.id,
                {
                    "unallocated":
                        portfolio.unallocated + order.amount * order.price
                }
            )

    def _sync_portfolio_with_cancelled_sell_order(self, order):
        position = self.position_repository.find({"id": order.position_id})
        self.position_repository.update(
            position.id,
            {
                "amount": position.amount + order.amount
            }
        )

    def _sync_portfolio_with_failed_buy_order(self, order):
        position = self.position_repository.find({"id": order.position_id})
        portfolio = self.portfolio_repository.get(position.portfolio_id)

        if OrderType.LIMIT.equals(order.type):
            self.portfolio_repository.update(
                portfolio.id,
                {
                    "unallocated":
                        portfolio.unallocated + order.amount * order.price
                }
            )

    def _sync_portfolio_with_failed_sell_order(self, order):
        position = self.position_repository.find({"id": order.position_id})
        self.position_repository.update(
            position.id,
            {
                "amount": position.amount + order.amount
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
