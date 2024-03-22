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


class FlaskTestBase(FlaskTestCase):
    portfolio_configurations = []
    market_credentials = []
    iaf_app = None

    def create_app(self):
        self.resource_directory = os.path.dirname(__file__)
        self.iaf_app: App = create_app(
            {RESOURCE_DIRECTORY: self.resource_directory}, web=True
        )

        # Add all portfolio configurations
        for portfolio_configuration in self.portfolio_configurations:
            self.iaf_app.add_portfolio_configuration(portfolio_configuration)

        self.iaf_app.container.market_service.override(MarketServiceStub(None))
        self.iaf_app.add_algorithm(Algorithm())

        # Add all market credentials
        for market_credential in self.market_credentials:
            self.iaf_app.add_market_credential(market_credential)

        algorithm = Algorithm()
        algorithm.add_strategy(StrategyOne)
        self.iaf_app.add_algorithm(algorithm)
        self.iaf_app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key="api_key",
                secret_key="secret_key",
            )
        )

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
