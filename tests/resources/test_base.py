import logging
import os
from decimal import Decimal
from unittest import TestCase

from flask_testing import TestCase as FlaskTestCase

from investing_algorithm_framework import create_app, App, \
    TradingStrategy, TimeUnit, OrderStatus
from investing_algorithm_framework.domain import RESOURCE_DIRECTORY, \
    ENVIRONMENT, Environment, BACKTEST_DATA_DIRECTORY_NAME, BACKTESTING_FLAG
from investing_algorithm_framework.infrastructure import BacktestOrderExecutor
from tests.resources.stubs import OrderExecutorTest, PortfolioProviderTest

logger = logging.getLogger(__name__)


class StrategyOne(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 10

    def run_strategy(self, algorithm, market_data):
        algorithm.create_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
            order_type="LIMIT",
        )


class TestBase(TestCase):
    portfolio_configurations = []
    config = {}
    external_balances = None
    external_orders = []
    initial_orders = []
    market_credentials = []
    market_data_source_service = None
    initialize = True
    resource_directory = os.path.dirname(__file__)
    data_providers = []

    def setUp(self) -> None:
        self.resource_directory = os.path.dirname(__file__)
        config = self.config
        config[RESOURCE_DIRECTORY] = self.resource_directory
        config[ENVIRONMENT] = Environment.TEST.value
        config[BACKTEST_DATA_DIRECTORY_NAME] = \
            "market_data_sources_for_testing"
        self.app: App = create_app(config=config)
        portfolio_provider_lookup = self.app.container\
            .portfolio_provider_lookup()
        portfolio_provider_lookup.reset()
        order_executor_test = OrderExecutorTest()
        order_executor_lookup = self.app.container.order_executor_lookup()
        order_executor_lookup.reset()
        self.app.add_order_executor(order_executor_test)
        portfolio_provider = PortfolioProviderTest()

        if self.external_balances is not None:
            portfolio_provider.external_balances = self.external_balances

        self.app.add_portfolio_provider(portfolio_provider)

        if len(self.data_providers) > 0:
            for data_provider in self.data_providers:
                self.app.add_data_provider(data_provider)

        if len(self.portfolio_configurations) > 0:
            for portfolio_configuration in self.portfolio_configurations:
                self.app.add_portfolio_configuration(
                    portfolio_configuration
                )

        # Add all market credentials
        if len(self.market_credentials) > 0:
            for market_credential in self.market_credentials:
                self.app.add_market_credential(market_credential)

        if self.initialize:
            self.app.initialize_config()
            self.app.initialize_storage()
            self.app.initialize_services()
            self.app.initialize_portfolios()

            if self.initial_orders is not None:
                for order in self.initial_orders:
                    created_order = self.app.context.create_order(
                        target_symbol=order.get_target_symbol(),
                        amount=order.get_amount(),
                        price=order.get_price(),
                        order_side=order.get_order_side(),
                        order_type=order.get_order_type()
                    )

                    # Update the order to the correct status
                    order_service = self.app.container.order_service()

                    if OrderStatus.CLOSED.value == order.get_status():
                        order_service.update(
                            created_order.get_id(),
                            {
                                "status": "CLOSED",
                                "filled": order.get_filled(),
                                "remaining": Decimal('0'),
                            }
                        )

    def tearDown(self) -> None:
        database_dir = os.path.join(
            self.resource_directory, "databases"
        )

        if os.path.exists(database_dir):
            for root, dirs, files in os.walk(database_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))

    def remove_database(self):

        database_dir = os.path.join(
            self.resource_directory, "databases"
        )

        if os.path.exists(database_dir):
            for root, dirs, files in os.walk(database_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))

    @classmethod
    def tearDownClass(cls) -> None:
        database_dir = os.path.join(
            cls.resource_directory, "databases"
        )

        if os.path.exists(database_dir):
            for root, dirs, files in os.walk(database_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))


class FlaskTestBase(FlaskTestCase):
    portfolio_configurations = []
    market_credentials = []
    iaf_app = None
    config = {}
    external_balances = {}
    initial_orders = []
    external_orders = []
    initialize = True
    resource_directory = os.path.dirname(__file__)

    def create_app(self):
        self.resource_directory = os.path.dirname(__file__)
        self.iaf_app: App = create_app(
            {
                RESOURCE_DIRECTORY: self.resource_directory
            },
            web=True
        )
        order_executor_lookup = self.iaf_app.container.order_executor_lookup()
        order_executor_lookup.reset()
        portfolio_provider_lookup = self.iaf_app.container\
            .portfolio_provider_lookup()
        portfolio_provider_lookup.reset()
        self.iaf_app.add_order_executor(OrderExecutorTest())
        portfolio_provider = PortfolioProviderTest()

        if self.external_balances is not None:
            portfolio_provider.external_balances = self.external_balances

        self.iaf_app.add_portfolio_provider(portfolio_provider)

        # if self.market_data_source_service is not None:
        #     self.app.container.market_data_source_service\
        #         .override(self.market_data_source_service)

        if len(self.portfolio_configurations) > 0:
            for portfolio_configuration in self.portfolio_configurations:
                self.iaf_app.add_portfolio_configuration(
                    portfolio_configuration
                )

        # Add all market credentials
        if len(self.market_credentials) > 0:
            for market_credential in self.market_credentials:
                self.iaf_app.add_market_credential(market_credential)

        if len(self.portfolio_configurations) > 0:
            for portfolio_configuration in self.portfolio_configurations:
                self.iaf_app.add_portfolio_configuration(
                    portfolio_configuration
                )

            # Add all market credentials
            if len(self.market_credentials) > 0:
                for market_credential in self.market_credentials:
                    self.iaf_app.add_market_credential(market_credential)

        if self.initialize:
            self.iaf_app.initialize_config()
            self.iaf_app.initialize_storage()
            self.iaf_app.initialize_services()
            self.iaf_app.initialize_portfolios()

        if self.initial_orders is not None:
            for order in self.initial_orders:
                created_order = self.app.context.create_order(
                    target_symbol=order.get_target_symbol(),
                    amount=order.get_amount(),
                    price=order.get_price(),
                    order_side=order.get_order_side(),
                    order_type=order.get_order_type()
                )

                # Update the order to the correct status
                order_service = self.app.container.order_service()

                if OrderStatus.CLOSED.value == order.get_status():
                    order_service.update(
                        created_order.get_id(),
                        {
                            "status": "CLOSED",
                            "filled": order.get_filled(),
                            "remaining": Decimal('0'),
                        }
                    )

        return self.iaf_app._flask_app

    def tearDown(self) -> None:
        database_dir = os.path.join(
            self.resource_directory, "databases"
        )

        if os.path.exists(database_dir):
            for root, dirs, files in os.walk(database_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))

    @classmethod
    def tearDownClass(cls) -> None:
        database_dir = os.path.join(
            cls.resource_directory, "databases"
        )

        if os.path.exists(database_dir):
            for root, dirs, files in os.walk(database_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
