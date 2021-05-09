from decimal import Decimal
from investing_algorithm_framework import OrderType, Order
from tests.resources import TestBase


class TestAlgorithmContext(TestBase):

    def setUp(self) -> None:
        super(TestAlgorithmContext, self).setUp()
        self.algorithm_context.add_portfolio_manager(self.portfolio_manager)
        self.algorithm_context.add_order_executor(self.order_executor)

        self.algorithm_context.perform_limit_order(
            broker="BINANCE",
            trading_pair="BTC-USDT",
            amount=10.3,
            price=10.40,
            order_type=OrderType.BUY
        )

        self.algorithm_context.perform_limit_order(
            broker="BINANCE",
            trading_pair="BTC-USDT",
            amount=10.3,
            price=12.00,
            order_type=OrderType.BUY
        )

        self.algorithm_context.perform_limit_order(
            broker="BINANCE",
            trading_pair="BTC/USDT",
            amount=20.3,
            price=11.00,
            order_type=OrderType.BUY
        )

    def test_performance_individual(self) -> None:

        total_costs = 0
        total_amount = 0

        for order in Order.query.filter_by(first_symbol="BTC").all():
            total_costs += order.amount * order.price
            total_amount += order.amount

        performance = self.algorithm_context.get_performance(
            second_symbol="USDT", broker="BINANCE", first_symbol="BTC"
        )

        total_worth = total_amount * self.portfolio_manager.get_price(
            second_symbol="USDT",
            first_symbol="BTC",
            algorithm_context=self.algorithm_context
        )

        self.assertEqual(
            Decimal((((total_worth - total_costs) / total_costs) * 100))
                .quantize(Decimal('1.00')),
            Decimal(performance).quantize(Decimal('1.00'))
        )
