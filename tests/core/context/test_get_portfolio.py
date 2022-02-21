from tests.resources import TestBase
from investing_algorithm_framework import SQLLitePortfolioManager, Portfolio


class MyPortfolioManagerOne(SQLLitePortfolioManager):
    market = "test"

    def get_unallocated(self, algorithm_context):
        return 1000

    def get_positions(self, algorithm_context):
        pass

    trading_symbol = "USDT"
    identifier = "MyPortfolioManagerOne"


class Test(TestBase):

    def setUp(self):
        super(Test, self).setUp()
        self.algo_app.algorithm.add_portfolio_manager(MyPortfolioManagerOne())

    def test(self) -> None:
        self.algo_app.start_algorithm()
        portfolio = self.algo_app.algorithm.get_portfolio()
        self.assertIsNotNone(portfolio)
        self.assertTrue(isinstance(portfolio, Portfolio))

    def test_without_identification(self):
        pass

    def test_without_portfolio_manager_registered(self):
        pass

    def test_retrieve_multiple(self):
        pass

    def test_without_trading_symbol(self):
        pass
