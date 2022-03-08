from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import Order, OrderType, \
    OrderSide, OrderStatus
from investing_algorithm_framework.configuration.constants import BINANCE


class BinanceOrderExecutorMixin:
    identifier = BINANCE

    def execute_order(
            self, order: Order, algorithm_context, **kwargs
    ) -> Order:
        market_service = algorithm_context.get_market_service(BINANCE)

        if OrderType.LIMIT.equals(order.get_type()):

            if OrderSide.BUY.equals(order.get_side()):
                market_service.create_limit_buy_order(
                    target_symbol=order.get_target_symbol(),
                    trading_symbol=order.get_trading_symbol(),
                    amount=order.get_amount_target_symbol(),
                    price=order.get_price
                )
                return order
            else:
                market_service.create_limit_sell_order(
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
                market_service.create_market_sell_order(
                    target_symbol=order.get_target_symbol(),
                    trading_symbol=order.get_trading_symbol(),
                    amount=order.get_amount_target_symbol(),
                )
            return order

    def check_order_status(
            self, order: Order, algorithm_context, **kwargs
    ) -> Order:
        market_service = algorithm_context.get_market_service(BINANCE)

        ref_order = market_service.get_order(
            order.get_reference_id(),
            order.get_target_symbol(),
            order.get_trading_symbol()
        )

        if ref_order is not None:

            if ref_order["info"]["status"] == "FILLED":
                order.set_status(OrderStatus.SUCCESS)
            if ref_order["info"]["status"] == "REJECTED	":
                order.set_status(OrderStatus.FAILED)
            if ref_order["info"]["status"] == "PENDING_CANCEL":
                order.set_status(OrderStatus.FAILED)
            if ref_order["info"]["status"] == "EXPIRED":
                order.set_status(OrderStatus.FAILED)

        return order
