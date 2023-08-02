import os

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration, OrderType, OrderSide, \
    OrderStatus
from tests.resources import TestBase, MarketServiceStub


class Test(TestBase):

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
                api_key="test",
                secret_key="test",
                trading_symbol="USDT"
            )
        )
        self.app.container.market_service.override(MarketServiceStub())
        self.app.create_portfolios()

    def test_create_limit_sell_order(self):
        self.app.run(number_of_iterations=1, sync=False)
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            side="BUY",
            percentage_of_portfolio=20
        )
        order_repository = self.app.container.order_repository()
        self.assertEqual(
            1, order_repository.count({"type": "LIMIT", "side": "BUY"})
        )
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.OPEN.value, order.status)
        self.assertEqual(20, order.amount)
        self.assertEqual(10, order.price)
        portfolio = self.app.algorithm.get_portfolio()
        self.assertEqual(1000, portfolio.net_size)
        self.assertEqual(800, portfolio.unallocated)
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        position = self.app.algorithm.get_position("BTC")
        print(position)
        order = self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            side="SELL",
            amount=20
        )
        self.assertEqual(20, order.amount)

def test_create_limit_sell_order_with_percentage_position(self):
        self.app.run(number_of_iterations=1, sync=False)
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            side="BUY",
            percentage_of_portfolio=20
        )
        order_repository = self.app.container.order_repository()
        self.assertEqual(
            1, order_repository.count({"type": "LIMIT", "side": "BUY"})
        )
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.OPEN.value, order.status)
        self.assertEqual(20, order.amount)
        self.assertEqual(10, order.price)
        portfolio = self.app.algorithm.get_portfolio()
        self.assertEqual(1000, portfolio.net_size)
        self.assertEqual(800, portfolio.unallocated)
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        position = self.app.algorithm.get_position("BTC")
        print(position)
        order = self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            price=10,
            side="SELL",
            percentage_of_position=20
        )
        # 20% of 20 = 4
        self.assertEqual(4, order.amount)