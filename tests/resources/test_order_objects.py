from investing_algorithm_framework import db, OrderSide
from investing_algorithm_framework.core.models import OrderType


class TestOrderAndPositionsObjectsMixin:

    @staticmethod
    def create_buy_order(amount, ticker, price, portfolio_manager):
        order = portfolio_manager.create_order(
            amount_target_symbol=amount,
            symbol=ticker,
            price=price,
            order_type=OrderType.LIMIT.value
        )
        portfolio_manager.add_order(order)

    @staticmethod
    def create_sell_order(amount, ticker, price, portfolio_manager):
        order = portfolio_manager.create_order(
            amount_target_symbol=amount,
            symbol=ticker,
            price=price,
            order_type=OrderType.LIMIT.value,
            order_side=OrderSide.SELL.value
        )
        portfolio_manager.add_order(order)

    @staticmethod
    def create_market_buy_order(amount, ticker, portfolio_manager):
        order = portfolio_manager.create_order(
            amount_target_symbol=amount,
            symbol=ticker,
            order_type=OrderType.MARKET.value,
            order_side=OrderSide.BUY.value
        )
        portfolio_manager.add_order(order)

    @staticmethod
    def create_market_sell_order(amount, ticker, portfolio_manager):
        order = portfolio_manager.create_order(
            amount_target_symbol=amount,
            symbol=ticker,
            order_type=OrderType.MARKET.value,
            order_side=OrderSide.SELL.value
        )
        portfolio_manager.add_order(order)
