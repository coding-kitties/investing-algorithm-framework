import os

from investing_algorithm_framework import create_app, TradingStrategy,\
    TimeUnit, RESOURCE_DIRECTORY, PortfolioConfiguration
from tests.resources import TestBase, MarketServiceStub


class StrategyOne(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 1

    def apply_strategy(self, algorithm, market_data):
        algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            side="BUY",
        )


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
                market="BITVAVO",
                api_key="test",
                secret_key="test",
                trading_symbol="USDT"
            )
        )
        self.app.container.market_service.override(MarketServiceStub())
        self.app.add_strategy(StrategyOne)

    def test_create_limit_buy_order(self):
        order_repository = self.app.container.order_repository()
        self.assertEqual(
            0, order_repository.count({"type": "LIMIT", "side": "BUY"})
        )
        self.app.run(number_of_iterations=1, sync=False)
        self.assertEqual(
            1, order_repository.count({"type": "LIMIT", "side": "BUY"})
        )
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual("PENDING", order.status)
