from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import Order, OrderType, \
    OrderSide, OrderStatus
from investing_algorithm_framework.configuration.constants import BINANCE


class BinanceOrderExecutorMixin:
    identifier = BINANCE

    def execute_limit_order(self, order: Order, algorithm_context, **kwargs):
        market_service = algorithm_context.get_market_service(BINANCE)

        if not OrderType.LIMIT.equals(order.order_type):
            raise OperationalException(
                "Provided order is not a limit order type"
            )

        if OrderSide.BUY.equals(order.order_side):
            market_service.create_limit_buy_order(
                target_symbol=order.target_symbol,
                trading_symbol=order.trading_symbol,
                amount=order.amount,
                price=order.price
            )
        else:
            market_service.create_limit_sell_order(
                target_symbol=order.target_symbol,
                trading_symbol=order.trading_symbol,
                amount=order.amount,
                price=order.price
            )

    def execute_market_order(self, order: Order, algorithm_context, **kwargs):
        market_service = algorithm_context.get_market_service(BINANCE)

        if not OrderType.MARKET.equals(order.order_type):
            raise OperationalException(
                "Provided order is not a market order type"
            )

        if OrderSide.BUY.equals(order.order_side):
            market_service.create_market_buy_order(
                target_symbol=order.target_symbol,
                trading_symbol=order.trading_symbol,
                amount=order.amount,
            )
        else:
            market_service.create_market_sell_order(
                target_symbol=order.target_symbol,
                trading_symbol=order.trading_symbol,
                amount=order.amount,
            )

    def get_order_status(self, order: Order, algorithm_context, **kwargs):
        market_service = algorithm_context.get_market_service(BINANCE)

        order = market_service.get_order(
            order.exchange_id, order.target_symbol, order.trading_symbol
        )

        if order is not None:

            if order["info"]["status"] == "FILLED":
                return OrderStatus.SUCCESS.value

            if order["info"]["status"] == "REJECTED	":
                return OrderStatus.FAILED.value

            if order["info"]["status"] == "PENDING_CANCEL":
                return OrderStatus.FAILED.value

            if order["info"]["status"] == "EXPIRED":
                return OrderStatus.FAILED.value

            return OrderStatus.PENDING.value
