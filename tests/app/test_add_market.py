import os
from unittest import TestCase
from unittest.mock import patch

from investing_algorithm_framework import create_app, OperationalException, \
    PositionMode, RESOURCE_DIRECTORY
from investing_algorithm_framework.domain import ENVIRONMENT, Environment
from investing_algorithm_framework.infrastructure import CCXTOrderExecutor, \
    CCXTPortfolioProvider
from tests.resources import OrderExecutorTest, PortfolioProviderTest


class HedgeOrderExecutorTest(OrderExecutorTest):

    def supports_position_mode(self, market, position_mode):
        return PositionMode(position_mode) in (
            PositionMode.NETTING, PositionMode.HEDGE
        )


class HedgePortfolioProviderTest(PortfolioProviderTest):

    def supports_position_mode(self, market, position_mode):
        return PositionMode(position_mode) in (
            PositionMode.NETTING, PositionMode.HEDGE
        )


class Test(TestCase):

    def setUp(self) -> None:
        self.resource_dir = os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "resources"
        )

    def test_add_market_from_environment_variables(self):
        with patch.dict(
            "os.environ",
            {
                "MARKET": "binance",
                "TRADING_SYMBOL": "eur",
                "INITIAL_BALANCE": "1500",
            },
            clear=False,
        ):
            app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
            app.add_market()

        portfolio_configurations = app.get_portfolio_configurations()
        self.assertEqual(1, len(portfolio_configurations))
        self.assertEqual("BINANCE", portfolio_configurations[0].market)
        self.assertEqual("EUR", portfolio_configurations[0].trading_symbol)
        self.assertEqual(
            1500.0, portfolio_configurations[0].initial_balance
        )

    def test_add(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(
            market="binance", trading_symbol="EUR",
        )

        # Check that a binance portfolio configuration was created
        portfolio_configurations = app.get_portfolio_configurations()
        self.assertEqual(len(portfolio_configurations), 1)
        self.assertEqual(
            portfolio_configurations[0].market, "BINANCE"
        )
        self.assertEqual(
            portfolio_configurations[0].trading_symbol, "EUR"
        )
        self.assertIsNone(
            portfolio_configurations[0].initial_balance
        )

        # Check that a binance market credential was created
        market_credentials = app.get_market_credentials()
        self.assertEqual(len(market_credentials), 1)

    def test_add_with_api_key(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(
            market="binance",
            trading_symbol="EUR",
            api_key="api_key",
            secret_key="secret_key"
        )

        potfolio_configurations = app.get_portfolio_configurations()[0]
        self.assertEqual(
            potfolio_configurations.market, "BINANCE"
        )
        self.assertEqual(
            potfolio_configurations.trading_symbol, "EUR"
        )
        self.assertIsNone(
            potfolio_configurations.initial_balance
        )

        market_credential = app.get_market_credentials()[0]
        self.assertEqual(
            market_credential.market, "BINANCE"
        )
        self.assertEqual(
            market_credential.api_key, "api_key"
        )
        self.assertEqual(
            market_credential.secret_key, "secret_key"
        )

    def test_add_with_hedge_position_mode(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(
            market="binance",
            trading_symbol="EUR",
            position_mode=PositionMode.HEDGE,
        )

        configuration = app.get_portfolio_configurations()[0]
        self.assertEqual(PositionMode.HEDGE, configuration.position_mode)

    def test_live_hedge_position_mode_fails_fast(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(
            market="binance",
            trading_symbol="EUR",
            position_mode=PositionMode.HEDGE,
        )

        with self.assertRaisesRegex(
            OperationalException,
            "Live PositionMode.HEDGE is unavailable",
        ):
            app._validate_live_position_modes(
                app.container.portfolio_configuration_service(),
                {ENVIRONMENT: Environment.PROD.value},
            )

    def test_live_hedge_requires_executor_and_provider_support(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(
            market="binance",
            trading_symbol="EUR",
            position_mode=PositionMode.HEDGE,
        )
        app.add_order_executor(HedgeOrderExecutorTest())

        with self.assertRaisesRegex(
            OperationalException, "no portfolio provider supports"
        ):
            app._validate_live_position_modes(
                app.container.portfolio_configuration_service(),
                {ENVIRONMENT: Environment.PROD.value},
            )

        app.add_portfolio_provider(HedgePortfolioProviderTest())
        app._validate_live_position_modes(
            app.container.portfolio_configuration_service(),
            {ENVIRONMENT: Environment.PROD.value},
        )

    def test_live_hedge_rejects_netting_only_executor(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(
            market="binance",
            trading_symbol="EUR",
            position_mode=PositionMode.HEDGE,
        )
        app.add_order_executor(OrderExecutorTest())
        app.add_portfolio_provider(HedgePortfolioProviderTest())

        with self.assertRaisesRegex(
            OperationalException, "cannot route directional HEDGE orders"
        ):
            app._validate_live_position_modes(
                app.container.portfolio_configuration_service(),
                {ENVIRONMENT: Environment.PROD.value},
            )

    def test_live_hedge_rejects_netting_only_provider(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(
            market="binance",
            trading_symbol="EUR",
            position_mode=PositionMode.HEDGE,
        )
        app.add_order_executor(HedgeOrderExecutorTest())
        app.add_portfolio_provider(PortfolioProviderTest())

        with self.assertRaisesRegex(
            OperationalException, "cannot reconcile independent HEDGE legs"
        ):
            app._validate_live_position_modes(
                app.container.portfolio_configuration_service(),
                {ENVIRONMENT: Environment.PROD.value},
            )

    def test_backtest_hedge_position_mode_is_allowed(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(
            market="binance",
            trading_symbol="EUR",
            position_mode=PositionMode.HEDGE,
        )

        app._validate_live_position_modes(
            app.container.portfolio_configuration_service(),
            {ENVIRONMENT: Environment.BACKTEST.value},
        )

    def test_ccxt_does_not_advertise_unimplemented_hedge_support(self):
        executor = CCXTOrderExecutor()
        provider = CCXTPortfolioProvider()

        self.assertTrue(executor.supports_position_mode(
            "binance", PositionMode.NETTING
        ))
        self.assertTrue(provider.supports_position_mode(
            "binance", PositionMode.NETTING
        ))
        self.assertFalse(executor.supports_position_mode(
            "binance", PositionMode.HEDGE
        ))
        self.assertFalse(provider.supports_position_mode(
            "binance", PositionMode.HEDGE
        ))
