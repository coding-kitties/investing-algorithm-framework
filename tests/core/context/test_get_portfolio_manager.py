from tests.resources import TestBase
from investing_algorithm_framework import SQLLitePortfolioManager


class MyPortfolioManagerOne(SQLLitePortfolioManager):

    def get_unallocated_synced(self, algorithm_context):
        return 1000

    def get_positions_synced(self, algorithm_context):
        pass

    trading_symbol = "USDT"
    identifier = "MyPortfolioManagerOne"


class MyPortfolioManagerTwo(SQLLitePortfolioManager):
    trading_symbol = "USDT"
    identifier = "MyPortfolioManagerTwo"

    def get_unallocated_synced(self, algorithm_context):
        return 1000

    def get_positions_synced(self, algorithm_context):
        pass


class Test(TestBase):

    def setUp(self):
        super(Test, self).setUp()
        self.algo_app.algorithm.add_portfolio_manager(MyPortfolioManagerOne())
        self.algo_app.algorithm.add_portfolio_manager(MyPortfolioManagerTwo())

    def test(self) -> None:
        my_portfolio_manager_one = self.algo_app.algorithm \
            .get_portfolio_manager(MyPortfolioManagerOne.identifier)

        self.assertTrue(
            my_portfolio_manager_one.identifier,
            MyPortfolioManagerOne.identifier
        )

        my_portfolio_manager_two = self.algo_app.algorithm \
            .get_portfolio_manager(MyPortfolioManagerTwo.identifier)

        self.assertTrue(
            my_portfolio_manager_two.identifier,
            MyPortfolioManagerTwo.identifier
        )

    def test_without_identification(self):
        pass

    def test_without_portfolio_manager_registered(self):
        pass

    def test_retrieve_multiple(self):
        pass

    def test_without_trading_symbol(self):
        pass
