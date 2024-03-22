import os

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration, Algorithm, MarketCredential
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
        algorithm = Algorithm()
        self.app.add_algorithm(algorithm)
        self.app.add_market_credential(
            MarketCredential(
                market="BINANCE",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BINANCE",
                trading_symbol="USDT"
            )
        )
        self.app.container.market_service.override(
            MarketServiceStub(self.app.container.market_credential_service())
        )

    def test_get_all(self):
        self.app.run(number_of_iterations=1)
        order_service = self.app.container.order_service()
        portfolio_service = self.app.container.portfolio_service()
        position_service = self.app.container.position_service()
        portfolio = portfolio_service.get_all()[0]
        order_service.create(
            {
                "portfolio_id": 1,
                "target_symbol": "BTC",
                "amount": 1,
                "trading_symbol": "USDT",
                "price": 10,
                "order_side": "BUY",
                "order_type": "LIMIT",
                "status": "OPEN",
            }
        )
        self.assertEqual(
            1, order_service.count({"portfolio": portfolio.identifier})
        )
        self.assertEqual(
            2, position_service.count({"portfolio": portfolio.id})
        )
        self.assertEqual(
            0, position_service.count({"portfolio": f"{portfolio.identifier}aeokgopge"})
        )
