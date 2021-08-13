import json
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from investing_algorithm_framework import PortfolioManager, Order, OrderSide, \
    Position


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
    'amount',
    'identifier',
    'executed',
    'id',
    'price',
    'target_symbol',
    'executed',
    "successful",
    'trading_symbol',
    'order_type',
    'order_side'
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
        super(Test, self).tearDown()
        self.algo_app.algorithm._portfolio_managers = {}

    def test_list_orders(self):
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_one)
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_two)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_one)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_two)

        position = Position.query.first()
        response = self.client.get(f"/api/orders/positions/{position.id}")
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            Order.query.filter_by(position=position).count(),
            len(data["items"])
        )
        self.assertEqual(SERIALIZATION_DICT, set(data.get("items")[0]))

    def test_list_orders_with_target_symbol_query_params(self):
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_one)
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_two)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_one)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_two)

        position = Position.query.first()
        query_params = {
            'target_symbol': position.symbol
        }

        response = self.client.get(
            f"/api/orders/positions/{position.id}",
            query_string=query_params
        )
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(
            Order.query
                .filter_by(position=position)
                .filter_by(target_symbol=position.symbol)
                .count(),
            len(data["items"])
        )
        self.assertEqual(SERIALIZATION_DICT, set(data.get("items")[0]))

    def test_list_orders_with_pending_query_params(self):
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_one)
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_two)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_one)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_two)

        position = Position.query.first()

        query_params = {
            'pending': True
        }

        response = self.client.get(
            f"/api/orders/positions/{position.id}",
            query_string=query_params
        )

        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            position.orders.filter_by(executed=True).count(),
            len(data["items"])
        )

    def test_list_orders_with_trading_symbol_query_params(self):
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_one)
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_two)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_one)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_two)

        position = self.portfolio_manager_one.get_positions()[0]

        query_params = {
            'trading_symbol': self.portfolio_manager_one.trading_currency
        }

        response = self.client.get(
            f"/api/orders/positions/{position.id}",
            query_string=query_params
        )
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            Order.query
                .filter_by(position=position)
                .filter_by(
                    trading_symbol=self.portfolio_manager_one.trading_currency
                )
                .count(),
            len(data["items"])
        )
        self.assertEqual(SERIALIZATION_DICT, set(data.get("items")[0]))

    def test_list_orders_with_order_side_query_params(self):
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_one)
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_two)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_one)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_two)

        position = Position.query.first()

        query_params = {
            'order_side': OrderSide.BUY.value
        }

        response = self.client.get(
            f"/api/orders/positions/{position.id}",
            query_string=query_params
        )
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            Order.query
                .filter_by(position=position)
                .filter_by(order_side=OrderSide.BUY.value)
                .count(),
            len(data["items"])
        )
        self.assertEqual(SERIALIZATION_DICT, set(data.get("items")[0]))

    def test_all_query_params(self):
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_one)
        self.create_buy_orders(5, self.TICKERS, self.portfolio_manager_two)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_one)
        self.create_sell_orders(2, self.TICKERS, self.portfolio_manager_two)

        position = Position.query.filter_by(symbol=self.TICKERS[0]).first()

        query_params = {
            'target_symbol': self.TICKERS[0],
            'trading_symbol': self.portfolio_manager_one.trading_currency,
            'order_side': OrderSide.BUY.value
        }

        response = self.client.get(
            f"/api/orders/positions/{position.id}",
            query_string=query_params
        )
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            Order.query.filter_by(
                position=position,
                order_side=OrderSide.BUY.value,
                trading_symbol=self.portfolio_manager_one.trading_currency,
                target_symbol=self.TICKERS[0]
            ).count(),
            len(data["items"])
        )
        self.assertEqual(SERIALIZATION_DICT, set(data.get("items")[0]))