import os
from unittest import TestCase

from investing_algorithm_framework import create_app, PortfolioConfiguration, \
    MarketCredential, Algorithm, AppMode, APP_MODE, RESOURCE_DIRECTORY, \
    AppHook
from tests.resources import PortfolioProviderTest, OrderExecutorTest
from tests.resources.strategies_for_testing.strategy_v2.strategy_v2 import \
    CrossOverStrategyV2
from tests.resources.strategies_for_testing.strategy_v1.strategy_v1 import \
    CrossOverStrategyV1



class OnStrategyRunAppHook(AppHook):

    def on_run(self, context) -> None:
        pass

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
            config={RESOURCE_DIRECTORY: self.resource_dir}
        )
        app.add_portfolio_provider(PortfolioProviderTest)
        app.add_order_executor(OrderExecutorTest)
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
        app.initialize_config()
        app.initialize_storage()
        app.initialize_services()
        self.assertIsNotNone(app.config)
        self.assertIsNone(app._flask_app)
        self.assertTrue(AppMode.DEFAULT.equals(app.config[APP_MODE]))
        order_service = app.container.order_service()
        self.assertEqual(0, order_service.count())

    def test_app_initialize_web(self):
        app = create_app(
            config={RESOURCE_DIRECTORY: self.resource_dir},
            web=True
        )
        app.add_portfolio_provider(PortfolioProviderTest)
        app.add_order_executor(OrderExecutorTest)
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
        app.initialize_config()
        app.initialize_storage()
        app.initialize_services()
        self.assertIsNotNone(app.config)
        self.assertIsNotNone(app._flask_app)
        self.assertTrue(AppMode.WEB.equals(app.config[APP_MODE]))
        order_service = app.container.order_service()
        self.assertEqual(0, order_service.count())

    def test_initialization_with_algorithm(self):
        app = create_app(
            config={RESOURCE_DIRECTORY: self.resource_dir},
            web=True
        )
        app.add_portfolio_provider(PortfolioProviderTest)
        app.add_order_executor(OrderExecutorTest)
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR",
            )
        )
        algorithm = Algorithm()
        algorithm.add_strategy(CrossOverStrategyV1)
        algorithm.add_strategy(CrossOverStrategyV2)
        app.add_algorithm(algorithm)
        app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        app.initialize_config()
        app.initialize_storage()
        app.initialize_services()
        self.assertEqual(2, len(algorithm.strategies))
        algorithm = app.get_algorithm()
        self.assertEqual(2, len(algorithm.strategies))

    def test_initialization_with_algorithm_and_on_strategy_run_hooks(self):
        app = create_app(
            config={RESOURCE_DIRECTORY: self.resource_dir},
            web=True
        )
        app.add_portfolio_provider(PortfolioProviderTest)
        app.add_order_executor(OrderExecutorTest)
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR",
            )
        )
        algorithm = Algorithm()
        algorithm.add_strategy(CrossOverStrategyV1)
        algorithm.add_strategy(CrossOverStrategyV2)
        app.add_algorithm(algorithm)
        app.on_strategy_run(OnStrategyRunAppHook())
        app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        app.initialize_config()
        app.initialize_storage()
        app.initialize_services()
        self.assertEqual(2, len(algorithm.strategies))
        algorithm = app.get_algorithm()
        self.assertEqual(2, len(algorithm.strategies))
        self.assertEqual(1, len(algorithm.on_strategy_run_hooks))

    def test_initialization_with_strategies_and_on_strategy_run_hooks(self):
        app = create_app(
            config={RESOURCE_DIRECTORY: self.resource_dir},
            web=True
        )
        app.add_portfolio_provider(PortfolioProviderTest)
        app.add_order_executor(OrderExecutorTest)
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR",
            )
        )
        app.add_strategy(CrossOverStrategyV1)
        app.add_strategy(CrossOverStrategyV2)
        app.on_strategy_run(OnStrategyRunAppHook())
        app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        app.initialize_config()
        app.initialize_storage()
        app.initialize_services()
        algorithm = app.get_algorithm()
        self.assertEqual(2, len(algorithm.strategies))
        self.assertEqual(1, len(algorithm.on_strategy_run_hooks))
