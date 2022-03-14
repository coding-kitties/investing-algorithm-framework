from datetime import datetime
from typing import List
from unittest import TestCase

from investing_algorithm_framework import App, PortfolioManager, Order
from investing_algorithm_framework import current_app
from investing_algorithm_framework.configuration.constants import \
    RESOURCES_DIRECTORY
from investing_algorithm_framework.core.models import AssetPrice


class PortfolioManagerTest(PortfolioManager):
    def get_orders(self, symbol, since: datetime = None,
                   algorithm_context=None, **kwargs) -> List[Order]:
        return []

    def get_prices(self, symbols, algorithm_context, **kwargs) -> List[AssetPrice]:
        return []

    identifier = "testTwo"

    def get_positions(self, symbol: str = None, lazy=False):
        return []


class Test(TestCase):

    def tearDown(self) -> None:
        current_app.reset()

    def test_from_class(self):
        app = App(
            config={"ENVIRONMENT": "test", RESOURCES_DIRECTORY: "goaoge"}
        )

        app.add_portfolio_manager(PortfolioManagerTest)
        self.assertEqual(1, len(app.algorithm._portfolio_managers))
        portfolio_manager = app.algorithm.get_portfolio_manager("testTwo")
        self.assertTrue(isinstance(portfolio_manager, PortfolioManagerTest))
        self.assertTrue(isinstance(portfolio_manager, PortfolioManagerTest))

    def test_from_object(self):
        app = App(
            config={"ENVIRONMENT": "test", RESOURCES_DIRECTORY: "goaoge"}
        )
        app.add_portfolio_manager(PortfolioManagerTest())
        self.assertEqual(1, len(app.algorithm._portfolio_managers))
        portfolio_manager = app.algorithm.get_portfolio_manager("testTwo")
        self.assertTrue(isinstance(portfolio_manager, PortfolioManagerTest))
        self.assertTrue(isinstance(portfolio_manager, PortfolioManagerTest))
