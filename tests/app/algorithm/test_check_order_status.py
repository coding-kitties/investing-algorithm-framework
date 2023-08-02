import os

from investing_algorithm_framework import create_app, TradingStrategy, \
    TimeUnit, RESOURCE_DIRECTORY, PortfolioConfiguration, OrderStatus
from tests.resources import TestBase, MarketServiceStub


class StrategyOne(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 1

    def apply_strategy(
        self,
        algorithm,
        market_data,
    ):
        algorithm.create_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            side="BUY",
            type="LIMIT",
            execute=True
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

    def test_check_order_status(self):
        order_repository = self.app.container.order_repository()
        position_repository = self.app.container.position_repository()
        self.app.run(number_of_iterations=1, sync=False)
        self.assertEqual(1, order_repository.count())
        self.assertEqual(2, position_repository.count())
        self.app.algorithm.order_service.check_pending_orders()
        self.assertEqual(1, order_repository.count())
        self.assertEqual(2, position_repository.count())
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.CLOSED.value, order.status)
        position = position_repository.find({"symbol": "BTC"})
        self.assertEqual(1, position.amount)
