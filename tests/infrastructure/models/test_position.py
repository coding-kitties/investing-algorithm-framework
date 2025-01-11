import os

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration, MarketCredential, Algorithm
from tests.resources import TestBase, MarketServiceStub


class Test(TestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="USDT"
        )
    ]
    external_balances = {
        "USDT": 1000
    }
    market_credentials = [
        MarketCredential(
            market="BITVAVO",
            api_key="",
            secret_key=""
        )
    ]

    # def setUp(self) -> None:
    #     self.resource_dir = os.path.abspath(
    #         os.path.join(
    #             os.path.join(
    #                 os.path.join(
    #                     os.path.join(
    #                         os.path.realpath(__file__),
    #                         os.pardir
    #                     ),
    #                     os.pardir
    #                 ),
    #                 os.pardir
    #             ),
    #             "resources"
    #         )
    #     )
    #     self.app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
    #     self.app.add_portfolio_configuration(
    #         PortfolioConfiguration(
    #             market="BITVAVO",
    #             trading_symbol="USDT"
    #         )
    #     )
    #     self.app.container.market_service.override(
    #         MarketServiceStub(self.app.container.market_credential_service())
    #     )
    #     algorithm = Algorithm()
    #     self.app.add_algorithm(algorithm)
    #     self.app.add_market_credential(
    #         MarketCredential(
    #             market="BITVAVO",
    #             api_key="api_key",
    #             secret_key="secret_key"
    #         )
    #     )
    #     self.app.initialize()

    # def tearDown(self):
    #     return super().tearDown()

    def test_store_position_amount(self):
        self.portfolio_service = self.app.container.portfolio_service()
        portfolio = self.portfolio_service.find({"market": "BITVAVO"})
        self.position_repository = self.app.container.position_repository()
        self.position_repository.create(
            {
                "symbol": "ADA",
                "amount": 2004.5303357979318,
                "portfolio_id": portfolio.id,
            }
        )
        position = self.position_repository.find(
            {"symbol": "ADA", "portfolio": portfolio.id}
        )
        self.assertEqual(position.amount, 2004.5303357979318)
        self.assertEqual(position.get_amount(), 2004.5303357979318)

    def test_position_update(self):
        self.portfolio_service = self.app.container.portfolio_service()
        portfolio = self.portfolio_service.find({"market": "BITVAVO"})
        self.position_repository = self.app.container.position_repository()
        self.position_repository.create(
            {
                "symbol": "ADA",
                "amount": 2004.5303357979318,
                "portfolio_id": portfolio.id,
            }
        )
        position = self.position_repository.find(
            {"symbol": "ADA", "portfolio": portfolio.id}
        )
        self.assertEqual(position.amount, 2004.5303357979318)
        self.assertEqual(position.get_amount(), 2004.5303357979318)
        position = self.position_repository.update(
            position.id,
            {
                "amount": position.get_amount() + 1000.0
            }
        )
        self.assertEqual(position.amount, 3004.5303357979318)
        self.assertEqual(position.get_amount(), 3004.5303357979318)
