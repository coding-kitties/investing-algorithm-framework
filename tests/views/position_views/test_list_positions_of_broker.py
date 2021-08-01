import json
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from investing_algorithm_framework import PortfolioManager, Position


class PortfolioManagerOne(PortfolioManager):
    base_currency = "USDT"
    broker = "KRAKEN"

    def get_initial_unallocated_size(self) -> float:
        return 1000


class PortfolioManagerTwo(PortfolioManager):
    base_currency = "BUSD"
    broker = "BINANCE"

    def get_initial_unallocated_size(self) -> float:
        return 2000


SERIALIZATION_DICT = {
    'symbol', 'amount', 'id', 'orders'
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
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_one)
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_two)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_one)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_two)

    def test_list_positions_of_broker(self):
        response = self.client.get(
            f"/api/positions/brokers/{self.portfolio_manager_one.broker}"
        )
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            Position.query
                .filter_by(portfolio=self.portfolio_manager_one.get_portfolio())
                .count(),
            len(data["items"])
        )
        self.assertEqual(SERIALIZATION_DICT, set(data.get("items")[0]))

    def test_list_positions_of_broker_with_symbol_query_params(self):
        query_params = {
            'symbol': self.TICKERS[0]
        }

        response = self.client.get(
            f"/api/positions/brokers/{PortfolioManagerOne.broker}",
            query_string=query_params
        )
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(1, len(data["items"]))
        self.assertEqual(SERIALIZATION_DICT, set(data.get("items")[0]))
