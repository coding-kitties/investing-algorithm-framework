import os
from unittest import TestCase

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    MarketCredential, Algorithm, AppMode, APP_MODE
from investing_algorithm_framework.domain import SQLALCHEMY_DATABASE_URI
from tests.resources import MarketServiceStub


class TestAppInitialize(TestCase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="BITVAVO",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]
    external_balances = {
        "EUR": 1000,
    }

    def setUp(self) -> None:
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

    def test_app_initialize_default(self):
        app = create_app(
            config={"test": "test", 'resource_directory': self.resource_dir}
        )
        app.container.market_service.override(
            MarketServiceStub(app.container.market_credential_service())
        )
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR",
            )
        )
        algorithm = Algorithm()
        app.add_algorithm(algorithm)
        app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        app.initialize()
        self.assertIsNotNone(app.config)
        self.assertIsNotNone(app._flask_app)
        self.assertTrue(AppMode.DEFAULT.equals(app.config[APP_MODE]))
        order_service = app.container.order_service()
        self.assertEqual(0, order_service.count())

    def test_app_initialize_web(self):
        app = create_app(
            config={"test": "test", 'resource_directory': self.resource_dir},
            web=True
        )
        app.container.market_service.override(MarketServiceStub(None))
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR",
            )
        )
        algorithm = Algorithm()
        app.add_algorithm(algorithm)
        app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        app.initialize()
        self.assertIsNotNone(app.config)
        self.assertIsNotNone(app._flask_app)
        self.assertTrue(AppMode.WEB.equals(app.config[APP_MODE]))
        order_service = app.container.order_service()
        self.assertEqual(0, order_service.count())

    def test_app_initialize_stateless(self):
        app = create_app(
            config={"test": "test"},
            stateless=True
        )
        app.container.market_service.override(MarketServiceStub(None))
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR"
            )
        )
        algorithm = Algorithm()
        app.add_algorithm(algorithm)
        app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        app.initialize()
        order_service = app.container.order_service()
        self.assertIsNotNone(app.config)
        self.assertIsNotNone(app._flask_app)
        self.assertTrue(AppMode.STATELESS.equals(app.config[APP_MODE]))
        self.assertEqual(app.config[SQLALCHEMY_DATABASE_URI], "sqlite://")
        self.assertEqual(0, order_service.count())
