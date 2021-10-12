from tests.resources import TestBase
from investing_algorithm_framework import PortfolioManager


class MyPortfolioManagerOne(PortfolioManager):
    trading_currency = "USDT"
    identifier = "MyPortfolioManagerOne"

    def get_initial_unallocated_size(self) -> float:
        return 1000


class MyPortfolioManagerTwo(PortfolioManager):
    trading_currency = "USDT"
    identifier = "MyPortfolioManagerTwo"

    def get_initial_unallocated_size(self) -> float:
        return 1000


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
