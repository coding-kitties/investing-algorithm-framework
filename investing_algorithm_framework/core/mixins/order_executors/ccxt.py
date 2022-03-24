from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import Order, OrderType, \
    OrderSide, OrderStatus


class CCXTOrderExecutorMixin:

    def execute_order(
        self, order: Order, algorithm_context, **kwargs
    ) -> Order:
        market_service = algorithm_context.get_market_service(
            market=self.market,
            api_key=self.api_key,
            secret_key=self.secret_key
        )

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
        market_service = algorithm_context.get_market_service(
            market=self.market,
            api_key=self.api_key,
            secret_key=self.secret_key
        )
        ref_order = market_service.get_order(order.get_reference_id())

        if ref_order is not None:

            status = OrderStatus.PENDING.value

            if ref_order["status"] == "open":
                status = OrderStatus.PENDING.value
            if ref_order["status"] == "closed":
                status = OrderStatus.CLOSED.value
            if ref_order["status"] == "canceled":
                status = OrderStatus.CANCELED.value
            if ref_order["status"] == "expired":
                status = OrderStatus.FAILED.value
            if ref_order["status"] == "rejected":
                status = OrderStatus.FAILED.value

            order.set_status(status)

        return order
