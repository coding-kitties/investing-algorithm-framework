from unittest import TestCase
import os
import logging
from investing_algorithm_framework.infrastructure.database import Session
from investing_algorithm_framework import create_app
from investing_algorithm_framework.domain import RESOURCE_DIRECTORY
from investing_algorithm_framework.app.web import create_flask_app
from investing_algorithm_framework.dependency_container import \
    DependencyContainer
from flask_testing import TestCase as FlaskTestCase
from tests.resources.stubs import MarketServiceStub

logger = logging.getLogger(__name__)


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

    def create_app(self):
        self.resource_directory = os.path.dirname(__file__)
        self.iaf_app = create_app({RESOURCE_DIRECTORY: self.resource_directory})
        self.iaf_app._flask_app = create_flask_app(self.iaf_app.config)
        self.iaf_app.container = DependencyContainer()
        self.iaf_app.algorithm = DependencyContainer.algorithm()

        for portfolio_configuration in self.portfolio_configurations:
            self.iaf_app.add_portfolio_configuration(
                   portfolio_configuration
            )
        self.iaf_app.container.market_service.override(MarketServiceStub())
        self.iaf_app.create_portfolios()
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