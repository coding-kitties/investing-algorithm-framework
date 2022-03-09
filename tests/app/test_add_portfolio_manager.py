from unittest import TestCase

from investing_algorithm_framework import App, PortfolioManager
from investing_algorithm_framework import current_app
from investing_algorithm_framework.configuration.constants import \
    RESOURCES_DIRECTORY


class PortfolioManagerTest(PortfolioManager):
    identifier = "testTwo"

    def get_positions(self, symbol: str = None, lazy=False):
        return []

    def get_orders(self, symbol: str = None, status=None, lazy=False):
        return []

    def get_price(
        self, target_symbol, trading_symbol, algorithm_context, **kwargs
    ) -> float:
        return 0.0


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
