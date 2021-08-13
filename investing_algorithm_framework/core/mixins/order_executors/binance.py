from investing_algorithm_framework.exchanges import BinanceExchangeClient
from investing_algorithm_framework.core.models import Order, OrderType, \
    OrderSide, db
from investing_algorithm_framework.core.exceptions import OperationalException


class BinanceOrderExecutorMixin(BinanceExchangeClient):
    identifier = "BINANCE"

    def execute_limit_order(self, order: Order, algorithm_context, **kwargs):

        if not OrderType.LIMIT.equals(order.order_type):
            raise OperationalException(
                "Provided order is not a limit order type"
            )

        if OrderSide.BUY.equals(order.order_side):
            self.create_limit_buy_order(
                target_symbol=order.target_symbol,
                trading_symbol=order.trading_symbol,
                amount=order.amount,
                price=order.price
            )
        else:
            self.create_limit_sell_order(
                target_symbol=order.target_symbol,
                trading_symbol=order.trading_symbol,
                amount=order.amount,
                price=order.price
            )

    def execute_market_order(self, order: Order, algorithm_context, **kwargs):

        if not OrderType.MARKET.equals(order.order_type):
            raise OperationalException(
                "Provided order is not a market order type"
            )

        if OrderSide.BUY.equals(order.order_side):
            self.create_market_buy_order(
                target_symbol=order.target_symbol,
                trading_symbol=order.trading_symbol,
                amount=order.amount,
            )
        else:
            self.create_market_sell_order(
                target_symbol=order.target_symbol,
                trading_symbol=order.trading_symbol,
                amount=order.amount,
            )

    def update_order_status(self, order: Order, algorithm_context, **kwargs):
        order = self.get_order(
            order.exchange_id, order.target_symbol, order.trading_symbol
        )

        if order is not None and order["info"]["status"] == "FILLED":
            order.update(db, {"executed": True, "successful": True})

        return order
