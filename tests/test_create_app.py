import os
from unittest import TestCase

from investing_algorithm_framework import create_app, \
    PortfolioConfiguration, Algorithm, MarketCredential
from investing_algorithm_framework.domain import RESOURCE_DIRECTORY
from tests.resources import MarketServiceStub


class TestCreateApp(TestCase):

    def setUp(self) -> None:
        super(TestCreateApp, self).setUp()
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.realpath(__file__),
                    os.pardir
                ),
                "resources"
            )
        )

    def test_create_app(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        self.assertIsNotNone(app)
        self.assertIsNone(app._flask_app)
        self.assertIsNotNone(app.container)
        self.assertIsNotNone(app.algorithm)

    def test_create_app_with_config(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        self.assertIsNotNone(app)
        self.assertIsNotNone(app.config)
        self.assertIsNone(app._flask_app)
        self.assertIsNotNone(app.container)
        self.assertIsNotNone(app.algorithm)

    def test_create_app_web(self):
        app = create_app(
            web=True, config={RESOURCE_DIRECTORY: self.resource_dir}
        )
        app.add_market_credential(
            MarketCredential(
                market="BINANCE",
                secret_key="secret_key",
                api_key="api_key"
            )
        )
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="USDT",
            )
        )
        app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        market_service = MarketServiceStub(app.container.market_credential_service())
        market_service.balances = {
            "USDT": 1000
        }
        app.container.market_service.override(
            market_service
        )
        app.initialize_config()
        app.initialize()
        self.assertIsNotNone(app)
        self.assertIsNotNone(app._flask_app)
        self.assertIsNotNone(app.container)
        self.assertIsNotNone(app.config)
        self.assertIsNotNone(app.algorithm)
