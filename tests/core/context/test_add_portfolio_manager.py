from investing_algorithm_framework import SQLLitePortfolioManager
from investing_algorithm_framework.core.exceptions import OperationalException
from tests.resources import TestBase


class MyPortfolioManagerOne(SQLLitePortfolioManager):
    identifier = "BINANCE"
    trading_currency = "USDT"

    def get_unallocated_synced(self, algorithm_context):
        return 1000

    def get_positions_synced(self, algorithm_context):
        pass


class Test(TestBase):

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
