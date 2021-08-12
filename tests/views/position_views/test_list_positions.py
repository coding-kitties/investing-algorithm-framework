import json
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from investing_algorithm_framework import PortfolioManager, Position


class PortfolioManagerOne(PortfolioManager):
    trading_currency = "USDT"
    identifier = "KRAKEN"

    def get_initial_unallocated_size(self) -> float:
        return 1000


class PortfolioManagerTwo(PortfolioManager):
    trading_currency = "BUSD"
    identifier = "BINANCE"

    def get_initial_unallocated_size(self) -> float:
        return 2000


SERIALIZATION_DICT = {
    'symbol', 'amount', 'id', 'orders', 'identifier'
}


class Test(TestBase, TestOrderAndPositionsObjectsMixin):
    TICKERS = [
        "BTC",
        "DOT",
        "ADA",
        "XRP",
        "ETH"
    ]

    def setUp(self):
        super(Test, self).setUp()
        self.portfolio_manager_one = PortfolioManagerOne()
        self.portfolio_manager_two = PortfolioManagerTwo()
        self.algo_app.algorithm.add_portfolio_manager(
            self.portfolio_manager_one
        )
        self.algo_app.algorithm.add_portfolio_manager(
            self.portfolio_manager_two
        )
        self.algo_app.algorithm.start()

    def tearDown(self):
        self.algo_app.algorithm.stop()
        super(Test, self).tearDown()

    def test_list_orders(self):
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_one)
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_two)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_one)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_two)

        response = self.client.get("/api/positions")
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(Position.query.count(), len(data["items"]))
        self.assertEqual(SERIALIZATION_DICT, set(data.get("items")[0]))

    def test_list_orders_with_target_symbol_query_params(self):
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_one)
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_two)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_one)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_two)

        query_params = {
            'symbol': self.TICKERS[0]
        }

        response = self.client.get("/api/positions", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(
            Position.query.filter_by(symbol=self.TICKERS[0]).count(),
            len(data["items"])
        )
        self.assertEqual(SERIALIZATION_DICT, set(data.get("items")[0]))
