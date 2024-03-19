import os

from investing_algorithm_framework import create_app, \
    TradingStrategy, TimeUnit, RESOURCE_DIRECTORY, MarketCredential, \
    PortfolioConfiguration, Algorithm
from tests.resources import TestBase, MarketServiceStub


class StrategyOne(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 2

    def apply_strategy(
        self,
        algorithm,
        market_date=None,
        **kwargs
    ):
        algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            order_side="BUY",
            price=10,
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
                market="BINANCE",
                trading_symbol="USDT"
            )
        )
        self.app.container.market_service.override(MarketServiceStub(None))
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        algorithm = Algorithm()
        algorithm.add_strategy(StrategyOne)
        self.app.add_algorithm(algorithm)

    def test_get_allocated(self):
        self.app.run(number_of_iterations=1)
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertNotEqual(0, self.app.algorithm.get_allocated())
        self.assertNotEqual(0, self.app.algorithm.get_allocated("BINANCE"))
