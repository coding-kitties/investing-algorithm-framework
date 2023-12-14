import os

from investing_algorithm_framework import create_app, PortfolioConfiguration
from investing_algorithm_framework.domain import SQLALCHEMY_DATABASE_URI
from tests.resources import TestBase, MarketServiceStub


class TestAppInitialize(TestBase):

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
                trading_symbol="USDT",
            )
        )
        app.initialize()
        self.assertIsNotNone(app.config)
        self.assertIsNone(app._flask_app)
        self.assertFalse(app.stateless)
        self.assertFalse(app.web)
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
                trading_symbol="USDT",
            )
        )
        app.initialize()
        self.assertIsNotNone(app.config)
        self.assertIsNotNone(app._flask_app)
        self.assertFalse(app.stateless)
        self.assertTrue(app.web)
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
                trading_symbol="USDT"
            )
        )
        app.initialize()
        order_service = app.container.order_service()
        self.assertIsNotNone(app.config)
        self.assertIsNone(app._flask_app)
        self.assertTrue(app.stateless)
        self.assertFalse(app.web)
        self.assertEqual(app.config[SQLALCHEMY_DATABASE_URI], "sqlite://")
        self.assertEqual(0, order_service.count())
