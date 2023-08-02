import os

from investing_algorithm_framework import create_app, TradingStrategy,\
    TimeUnit, RESOURCE_DIRECTORY, PortfolioConfiguration, OrderStatus
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

    def test_create_limit_buy_order(self):
        self.app.run(number_of_iterations=1, sync=False)
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            side="BUY",
        )
        order_repository = self.app.container.order_repository()
        self.assertEqual(
            1, order_repository.count({"type": "LIMIT", "side": "BUY"})
        )
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.OPEN.value, order.status)

    def test_create_limit_buy_order_with_percentage_of_portfolio(self):
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
