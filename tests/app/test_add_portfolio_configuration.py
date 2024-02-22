import os

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    RESOURCE_DIRECTORY
from investing_algorithm_framework.dependency_container import \
    DependencyContainer
from tests.resources import TestBase, MarketServiceStub


class Test(TestBase):

    def setUp(self) -> None:
        DependencyContainer.market_service.override(
            MarketServiceStub(market_credential_service=None)
        )
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.realpath(__file__),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )

    def test_add(self):
        app = create_app(
            config={"test": "test", RESOURCE_DIRECTORY: self.resource_dir}
        )
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="USDT",
            )
        )
        app.container.market_service.override(MarketServiceStub(None))
        portfolio_configuration_service = app.container\
            .portfolio_configuration_service()
        self.assertIsNotNone(portfolio_configuration_service.get("BITVAVO"))
        app.run(number_of_iterations=1)
        self.assertEqual(app.algorithm.portfolio_service.count(), 1)
        self.assertEqual(app.algorithm.get_unallocated(), 1000)
