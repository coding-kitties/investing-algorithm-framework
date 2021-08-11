from investing_algorithm_framework import PortfolioManager
from investing_algorithm_framework.core.exceptions import OperationalException
from tests.resources import TestBase


class MyPortfolioManagerOne(PortfolioManager):
    identifier = "BINANCE"
    trading_currency = "USDT"

    def get_initial_unallocated_size(self) -> float:
        pass


class Test(TestBase):

    def setUp(self) -> None:
        super(Test, self).setUp()

    def tearDown(self):
        self.algo_app.algorithm._portfolio_managers = {}

    def test(self) -> None:
        self.algo_app.algorithm.add_portfolio_manager(MyPortfolioManagerOne())
        self.assertTrue(
            MyPortfolioManagerOne.identifier in
            self.algo_app.algorithm._portfolio_managers
        )

    def test_duplicate(self):
        self.algo_app.algorithm.add_portfolio_manager(MyPortfolioManagerOne())
        self.assertTrue(
            MyPortfolioManagerOne.identifier in
            self.algo_app.algorithm._portfolio_managers
        )
        with self.assertRaises(OperationalException):
            self.algo_app.algorithm.add_portfolio_manager(
                MyPortfolioManagerOne()
            )
