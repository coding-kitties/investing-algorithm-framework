import os
import shutil
from unittest import TestCase
from unittest.mock import patch

from investing_algorithm_framework import create_app, TradingStrategy, \
    TimeUnit, PortfolioConfiguration, RESOURCE_DIRECTORY, \
    Algorithm, MarketCredential, Schedule, AppHook, OperationalException
from investing_algorithm_framework.infrastructure.database import \
    teardown_sqlalchemy
from tests.resources import random_string, OrderExecutorTest, \
    PortfolioProviderTest


class EmptyStrategy(TradingStrategy):
    schedule = Schedule.every(2, TimeUnit.SECOND)


class RecordingAppHook(AppHook):
    calls = 0

    def on_run(self, context) -> None:
        RecordingAppHook.calls += 1


class RaisingAppHook(AppHook):

    def on_run(self, context) -> None:
        raise OperationalException("hook failure")


class TestValidate(TestCase):

    def setUp(self) -> None:
        super().setUp()
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "resources"
            )
        )
        RecordingAppHook.calls = 0

    def tearDown(self) -> None:
        super().tearDown()
        teardown_sqlalchemy()
        for subdir in ("databases", "backtest_databases"):
            path = os.path.join(self.resource_dir, subdir)
            if os.path.exists(path):
                shutil.rmtree(path, ignore_errors=True)

    def _create_app(self, market="BINANCE"):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_portfolio_provider(PortfolioProviderTest)
        app.add_order_executor(OrderExecutorTest)
        app.add_portfolio_configuration(
            PortfolioConfiguration(market=market, trading_symbol="EUR")
        )
        app.add_market_credential(
            MarketCredential(
                market=market,
                api_key=random_string(10),
                secret_key=random_string(10),
            )
        )
        app.add_strategy(EmptyStrategy)
        return app

    def test_validate_does_not_raise_for_valid_app(self):
        app = self._create_app()
        app.validate()

    def test_validate_runs_on_initialize_hooks(self):
        app = self._create_app()
        app.on_initialize(RecordingAppHook)
        app.validate()
        self.assertEqual(1, RecordingAppHook.calls)

    def test_validate_propagates_on_initialize_hook_errors(self):
        app = self._create_app()
        app.on_initialize(RaisingAppHook)
        with self.assertRaises(OperationalException):
            app.validate()

    def test_validate_raises_when_no_portfolio_configured(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_portfolio_provider(PortfolioProviderTest)
        app.add_order_executor(OrderExecutorTest)
        app.add_strategy(EmptyStrategy)
        with self.assertRaises(OperationalException):
            app.validate()

    def test_validate_require_portfolio_false_skips_portfolio_check(self):
        """A strategy-only sandbox check should not require credentials."""
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_strategy(EmptyStrategy)
        app.add_market_credential(MarketCredential(market="BINANCE"))
        market_credential_service = app.container.market_credential_service()

        with patch.object(
            market_credential_service,
            "initialize",
            wraps=market_credential_service.initialize,
        ) as initialize:
            app.validate(require_portfolio=False)

        initialize.assert_not_called()

    def test_validate_require_portfolio_false_still_runs_hooks(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_strategy(EmptyStrategy)
        app.on_initialize(RecordingAppHook)
        app.validate(require_portfolio=False)
        self.assertEqual(1, RecordingAppHook.calls)

    def test_validate_does_not_start_event_loop_or_flask(self):
        app = self._create_app()
        app.validate()
        self.assertIsNone(app._web_app)
        self.assertFalse(app.has_run("EmptyStrategy"))

    def test_validate_does_not_place_orders(self):
        app = self._create_app()
        app.validate()
        order_service = app.container.order_service()
        self.assertEqual(0, order_service.count())

    def test_validate_can_be_followed_by_run(self):
        """`validate()` should be safely callable before `run()` without
        leaving the app in a broken state for the subsequent real run."""
        app = self._create_app()
        app.validate()
        app.run(number_of_iterations=1)
        self.assertTrue(app.has_run("EmptyStrategy"))
