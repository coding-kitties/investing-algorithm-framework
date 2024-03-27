import logging
import os
from unittest import TestCase

from flask_testing import TestCase as FlaskTestCase

from investing_algorithm_framework import create_app, Algorithm, App, \
    MarketCredential, TradingStrategy, TimeUnit
from investing_algorithm_framework.domain import RESOURCE_DIRECTORY
from investing_algorithm_framework.infrastructure.database import Session
from tests.resources.stubs import MarketServiceStub

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
    algorithm = Algorithm()
    external_balances = {}
    external_orders = []
    external_available_symbols = []
    market_credentials = []
    market_service = MarketServiceStub(None)
    initialize = True
    resource_directory = os.path.dirname(__file__)

    def setUp(self) -> None:
        self.remove_database()
        self.resource_directory = os.path.dirname(__file__)
        config = self.config
        config[RESOURCE_DIRECTORY] = self.resource_directory
        self.app: App = create_app(config=config)
        self.market_service.symbols = self.external_available_symbols
        self.market_service.balances = self.external_balances
        self.market_service.orders = self.external_orders
        self.app.container.market_service.override(self.market_service)

        if len(self.portfolio_configurations) > 0:
            for portfolio_configuration in self.portfolio_configurations:
                self.app.add_portfolio_configuration(
                    portfolio_configuration
                )

        self.app.add_algorithm(self.algorithm)

        # Add all market credentials
        if len(self.market_credentials) > 0:
            for market_credential in self.market_credentials:
                self.app.add_market_credential(market_credential)

        if self.initialize:
            self.app.initialize()

    def tearDown(self) -> None:
        database_path = os.path.join(
            self.resource_directory, "databases/prod-database.sqlite3"
        )

        if os.path.exists(database_path):
            session = Session()
            session.commit()
            session.close()

            try:
                os.remove(database_path)
            except Exception as e:
                logger.error(e)

    def remove_database(self):

        try:
            database_path = os.path.join(
                self.resource_directory, "databases/prod-database.sqlite3"
            )

            if os.path.exists(database_path):
                os.remove(database_path)
        except Exception as e:
            logger.error(e)


class FlaskTestBase(FlaskTestCase):
    portfolio_configurations = []
    market_credentials = []
    iaf_app = None
    config = {}
    algorithm = Algorithm()
    external_balances = {}
    external_orders = []
    external_available_symbols = []
    market_service = MarketServiceStub(None)
    initialize = True

    def create_app(self):
        self.resource_directory = os.path.dirname(__file__)
        self.iaf_app: App = create_app(
            {RESOURCE_DIRECTORY: self.resource_directory}, web=True
        )
        self.market_service.symbols = self.external_available_symbols
        self.market_service.balances = self.external_balances
        self.market_service.orders = self.external_orders
        self.iaf_app.container.market_service.override(self.market_service)

        if self.initialize:

            if len(self.portfolio_configurations) > 0:
                for portfolio_configuration in self.portfolio_configurations:
                    self.iaf_app.add_portfolio_configuration(
                        portfolio_configuration
                    )

                self.iaf_app.add_algorithm(self.algorithm)

                # Add all market credentials
                if len(self.market_credentials) > 0:
                    for market_credential in self.market_credentials:
                        self.iaf_app.add_market_credential(market_credential)

                self.iaf_app.initialize()

        return self.iaf_app._flask_app

    def tearDown(self) -> None:
        database_path = os.path.join(
            os.path.dirname(__file__), "databases/prod-database.sqlite3"
        )

        if os.path.exists(database_path):
            session = Session()
            session.commit()
            session.close()

            try:
                os.remove(database_path)
            except Exception as e:
                logger.error(e)
