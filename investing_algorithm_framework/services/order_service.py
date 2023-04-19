from investing_algorithm_framework.domain import OrderType, OrderSide, \
    OperationalException, OrderStatus
from investing_algorithm_framework.services.repository_service \
    import RepositoryService


class OrderService(RepositoryService):

    def __init__(
        self,
        order_repository,
        market_service,
        position_repository,
        portfolio_repository,
        portfolio_configuration_service,
    ):
        super(OrderService, self).__init__(order_repository)
        self.order_repository = order_repository
        self.market_service = market_service
        self.position_repository = position_repository
        self.portfolio_repository = portfolio_repository
        self.portfolio_configuration_service = portfolio_configuration_service

    def create(self, data, execute=True, validate = True):
        portfolio_id = data["portfolio_id"]
        portfolio = self.portfolio_repository.get(portfolio_id)

        if validate:
            self.validate_order(data, portfolio)

        del data["portfolio_id"]
        symbol = data["target_symbol"]
        self.validate_order(data, portfolio)

        if not self.position_repository.exists(
            {"portfolio": portfolio.identifier, "symbol": symbol}
        ):
            self.position_repository\
                .create({"portfolio_id": portfolio.id, "symbol": symbol})
            position = self.position_repository \
                .find({"portfolio": portfolio.identifier, "symbol": symbol})
        else:
            position = self.position_repository\
                .find({"portfolio": portfolio.identifier, "symbol": symbol})

        data["position_id"] = position.id
        order = self.order_repository.create(data)
        order_id = order.id

        if execute:
            portfolio.configuration = self.portfolio_configuration_service\
                .get(portfolio.identifier)
            self.execute_order(order_id, portfolio)

        return order

    def execute_order(self, order_id, portfolio):
        self.market_service.initialize(portfolio.configuration)
        order = self.get(order_id)

        if OrderType.LIMIT.equals(order.get_type()):

            if OrderSide.BUY.equals(order.get_side()):
                self.market_service.create_limit_buy_order(
                    target_symbol=order.get_target_symbol(),
                    trading_symbol=order.get_trading_symbol(),
                    amount=order.get_amount_target_symbol(),
                    price=order.get_price
                )
                trading_symbol_position = self.position_repository \
                    .find(
                        {"portfolio": portfolio.identifier,
                         "symbol": order.trading_symbol}
                )
                self.position_repository.update(
                    trading_symbol_position.id,
                    {"amount": trading_symbol_position.amount
                        - order.amount_trading_symbol}
                )
                return order
            else:
                self.market_service.create_limit_sell_order(
                    target_symbol=order.get_target_symbol(),
                    trading_symbol=order.get_trading_symbol(),
                    amount=order.get_amount_target_symbol(),
                    price=order.get_price()
                )
                return order
        else:
            if OrderSide.BUY.equals(order.get_side()):
                raise OperationalException("Market buy order not supported")
            else:
                self.market_service.create_market_sell_order(
                    target_symbol=order.get_target_symbol(),
                    trading_symbol=order.get_trading_symbol(),
                    amount=order.get_amount_target_symbol(),
                )
            return order

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
                    "portfolio": portfolio.identifier
                }
        ):
            raise OperationalException(
                f"Can't add sell order to non existing position"
            )

        position = self.position_repository\
            .find(
                {
                    "symbol": order_data["target_symbol"],
                    "portfolio": portfolio.identifier
                }
            )

        if position.amount < order_data["amount_target_symbol"]:
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
        total_price = order_data["amount_target_symbol"] * \
                      order_data["price"]
        unallocated_position = self.position_repository\
            .find(
                {"portfolio": portfolio.identifier, "symbol": portfolio.trading_symbol}
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

            if "amount_trading_symbol" not in order_data:
                raise OperationalException(
                    f"Market order needs an amount specified in the trading "
                    f"symbol {order_data['trading_symbol']}"
                )

            if order_data['amount_trading_symbol'] > portfolio.unallocated:
                raise OperationalException(
                    f"Market order amount {order_data['amount_trading_symbol']} "
                    f"{portfolio.trading_symbol.upper()} is larger then "
                    f"unallocated {portfolio.unallocated} "
                    f"{portfolio.trading_symbol.upper()}"
                )
        else:
            position = self.position_repository\
                .find(
                    {
                        "symbol": order_data["target_symbol"],
                        "portfolio": portfolio.identifier
                    }
                )

            if position is None:
                raise OperationalException(
                    "Can't add market sell order to non existing position"
                )

            if order_data['amount_target_symbol'] > position.amount:
                raise OperationalException(
                    "Sell order amount larger then position size"
                )

    def check_pending_orders(self):
        pending_orders = self.get_all({"status": OrderStatus.PENDING.value})

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

            updated_order = self.update(
                order.id, {"status": external_order.status}
            )
            position = self.position_repository.get(updated_order.position_id)

            if OrderStatus.SUCCESS.equals(updated_order.status):

                if OrderSide.BUY.equals(updated_order.side):
                    self.position_repository.update(
                        position.id,
                        {"amount": position.amount + order.amount_target_symbol}
                    )
                else:
                    self.position_repository.update(
                        position.id,
                        {"amount": position.amount - order.amount_target_symbol}
                    )
                    trading_symbol_position = self.position_repository.find(
                        {"portfolio": portfolio.identifier,
                         "symbol": order.trading_symbol}
                    )

                    if OrderType.LIMIT.equals(order.type):
                        self.position_repository.update(
                            trading_symbol_position.id,
                            {
                                "amount":
                                    trading_symbol_position.amount
                                    + order.amount_trading_symbol
                            }
                        )
                    else:
                        updated_order = self.order_repository.update(
                            updated_order.id, {"price": external_order.price}
                        )

                        if OrderType.MARKET.equals(updated_order.type):
                            updated_order = self.order_repository.update(
                                updated_order.id,
                                {
                                    "amount_trading_symbol":
                                        updated_order.amount_target_symbol
                                        * updated_order.price
                                }
                            )

                        self.position_repository.update(
                            trading_symbol_position.id,
                            {
                                "amount":
                                    trading_symbol_position.amount
                                    + updated_order.amount_trading_symbol
                            }
                        )
