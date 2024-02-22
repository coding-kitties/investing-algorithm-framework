import os

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration, OrderStatus
from tests.resources import TestBase, MarketServiceStub


class Test(TestBase):

    def count_decimals(self, number):
        decimal_str = str(number)
        if '.' in decimal_str:
            return len(decimal_str.split('.')[1])
        else:
            return 0

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.join(
                            os.path.realpath(__file__),
                            os.pardir
                        ),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )
        self.app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="USDT"
            )
        )
        self.app.container.market_service.override(MarketServiceStub(None))
        self.app.initialize()

    def test_create_limit_buy_order(self):
        self.app.run(number_of_iterations=1)
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        order_repository = self.app.container.order_repository()
        self.assertEqual(
            1, order_repository.count({"order_type": "LIMIT", "order_side": "BUY"})
        )
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.OPEN.value, order.status)

    def test_create_limit_buy_order_with_percentage_of_portfolio(self):
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="BUY",
            percentage_of_portfolio=20,
            precision=0
        )
        order_repository = self.app.container.order_repository()
        self.assertEqual(
            1, order_repository.count({"order_type": "LIMIT", "order_side": "BUY"})
        )
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.OPEN.value, order.status)
        self.assertEqual(20, order.get_amount())
        self.assertEqual(10, order.get_price())
        portfolio = self.app.algorithm.get_portfolio()
        self.assertEqual(1000, portfolio.get_net_size())
        self.assertEqual(800, portfolio.get_unallocated())
