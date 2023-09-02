import os
from investing_algorithm_framework import create_app, Config, \
    PortfolioConfiguration
from investing_algorithm_framework.domain import RESOURCE_DIRECTORY
from tests.resources import TestBase, MarketServiceStub


class TestCreateApp(TestBase):

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
        self.assertFalse(app._stateless)
        self.assertIsNotNone(app.container)
        self.assertIsNone(app.algorithm)

    def test_create_app_with_config(self):
        config = Config(
            resource_directory=self.resource_dir
        )
        app = create_app(config=config)
        self.assertIsNotNone(app)
        self.assertIsNotNone(app.config)
        self.assertIsNone(app._flask_app)
        self.assertFalse(app._stateless)
        self.assertIsNotNone(app.container)
        self.assertIsNone(app.algorithm)

    def test_create_app_stateless(self):
        app = create_app(stateless=True, config={})
        self.assertIsNotNone(app)
        self.assertIsNotNone(app.config)
        self.assertTrue(app._stateless)
        self.assertIsNotNone(app.container)
        self.assertIsNotNone(app.config)
        self.assertIsNone(app.algorithm)

    def test_create_app_web(self):
        app = create_app(
            web=True, config={RESOURCE_DIRECTORY: self.resource_dir}
        )
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="USDT",
                api_key="test",
                secret_key="test"
            )
        )
        app.container.market_service.override(MarketServiceStub())
        app.initialize()
        self.assertIsNotNone(app)
        self.assertIsNotNone(app._flask_app)
        self.assertIsNotNone(app.container)
        self.assertIsNotNone(app.config)
        self.assertIsNotNone(app.algorithm)

