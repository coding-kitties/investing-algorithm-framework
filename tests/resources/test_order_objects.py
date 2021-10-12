from investing_algorithm_framework import db, OrderSide
from investing_algorithm_framework.core.models import OrderType


class TestOrderAndPositionsObjectsMixin:

    @staticmethod
    def create_buy_order(amount, ticker, price, portfolio_manager):
        order = portfolio_manager.create_order(
            amount=amount,
            symbol=ticker,
            price=price,
            order_type=OrderType.LIMIT.value
        )
        portfolio_manager.add_order(order)
        order.set_pending()

    @staticmethod
    def create_sell_order(amount, ticker, price, portfolio_manager):
        order = portfolio_manager.create_order(
            amount=amount,
            symbol=ticker,
            price=price,
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value
        )
        portfolio_manager.add_order(order)
        order.set_pending()
