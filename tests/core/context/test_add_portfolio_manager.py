from typing import List

from investing_algorithm_framework import SQLLitePortfolioManager, Position, \
    Order
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import AssetPrice
from tests.resources import TestBase


class MyPortfolioManagerOne(SQLLitePortfolioManager):
    identifier = "BINANCE"
    trading_currency = "USDT"

    def get_positions(self, algorithm_context=None, **kwargs) -> List[Position]:
        return [
            Position(target_symbol="USDT", amount=1000)
        ]

    def get_orders(self, algorithm_context, **kwargs) -> List[Order]:
        pass

    def get_prices(self, symbols, algorithm_context, **kwargs) -> List[AssetPrice]:
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
