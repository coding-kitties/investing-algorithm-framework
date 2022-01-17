from unittest import TestCase
from investing_algorithm_framework import App, PortfolioManager, OrderType, \
    OrderSide
from investing_algorithm_framework.configuration.constants import \
    RESOURCES_DIRECTORY
from investing_algorithm_framework import current_app


class PortfolioManagerTest(PortfolioManager):
    identifier = "testTwo"

    def get_unallocated(self, algorithm_context, sync=False):
        pass

    def get_allocated(self, algorithm_context, sync=False):
        pass

    def initialize(self, algorithm_context):
        pass

    def get_portfolio(self, algorithm_context):
        pass

    def get_positions(self, symbol: str = None, lazy=False):
        pass

    def get_orders(self, symbol: str = None, status=None, lazy=False):
        pass

    def create_order(self, symbol, price=None, amount_trading_symbol=None,
                     amount_target_symbol=None,
                     order_type=OrderType.LIMIT.value,
                     order_side=OrderSide.BUY.value, context=None,
                     validate_pair=True):
        pass

    def add_order(self, order):
        pass


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
