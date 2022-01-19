import json
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from tests.resources.serialization_dicts import order_serialization_dict
from investing_algorithm_framework import Order, OrderSide, db, OrderStatus, \
    Portfolio, Position


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.start_algorithm()

        order = self.algo_app.algorithm.create_limit_buy_order(
            self.TARGET_SYMBOL_A,
            self.BASE_SYMBOL_A_PRICE,
            1,
            True
        )
        order.save(db)
        order.set_executed()

        order = self.algo_app.algorithm.create_limit_buy_order(
            self.TARGET_SYMBOL_B,
            self.BASE_SYMBOL_B_PRICE,
            1,
            True
        )
        order.save(db)
        order.set_executed()

        order = self.algo_app.algorithm.create_limit_sell_order(
            self.TARGET_SYMBOL_B,
            self.BASE_SYMBOL_B_PRICE,
            1,
            True
        )
        order.save(db)
        order.set_executed()

    def test_list_orders(self):
        response = self.client.get("/api/orders")
        self.assert200(response)
        data = json.loads(response.data.decode())
        self.assertEqual(Order.query.count(), len(data["items"]))
        self.assertEqual(order_serialization_dict, set(data.get("items")[0]))

    def test_list_orders_with_position(self):
        query_params = {'position': self.TARGET_SYMBOL_B}
        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())

        position_ids = Position.query\
            .filter_by(symbol=self.TARGET_SYMBOL_B)\
            .with_entities(Position.id)

        self.assertEqual(
            Order.query.filter(Order.position_id.in_(position_ids)).count(),
            len(data["items"])
        )

        query_params = {'position': self.TARGET_SYMBOL_C}
        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            0,
            len(data["items"])
        )

    def test_list_orders_with_identifier(self):
        query_params = {'identifier': "test"}
        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())

        portfolio = Portfolio.query.filter_by(identifier="test").first()

        position_ids = portfolio.positions.with_entities(Position.id)

        self.assertEqual(
            Order.query.filter(Order.position_id.in_(position_ids)).count(),
            len(data["items"])
        )

        query_params = {'identifier': "random"}
        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            0,
            len(data["items"])
        )

    def test_list_orders_with_target_symbol_query_params(self):
        query_params = {'target_symbol': self.TARGET_SYMBOL_A}
        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            Order.query.filter_by(target_symbol=self.TARGET_SYMBOL_A).count(),
            len(data["items"])
        )

        query_params = {'target_symbol': self.TARGET_SYMBOL_B}
        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data)

        self.assertEqual(
            Order.query.filter_by(target_symbol=self.TARGET_SYMBOL_B).count(),
            data["total"]
        )

    def test_list_orders_with_trading_symbol_query_params(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        query_params = {
            'trading_symbol': portfolio_manager.trading_symbol
        }

        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            Order.query.filter_by(
                trading_symbol=portfolio_manager.trading_symbol
            ).count(),
            len(data["items"])
        )

    def test_list_orders_with_pending_query_params(self):
        query_params = {
            'status': OrderStatus.PENDING.value
        }

        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            Order.query.filter_by(status=OrderStatus.PENDING.value).count(),
            len(data["items"])
        )

    def test_list_orders_with_success_query_params(self):
        query_params = {
            'status': OrderStatus.SUCCESS.value
        }

        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            Order.query.filter_by(status=OrderStatus.SUCCESS.value).count(),
            len(data["items"])
        )

    def test_list_orders_with_order_side_query_params(self):

        query_params = {
            'order_side': OrderSide.BUY.value
        }

        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            Order.query.filter_by(
                order_side=OrderSide.BUY.value
            ).count(),
            len(data["items"])
        )

        query_params = {
            'order_side': OrderSide.SELL.value
        }

        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            Order.query.filter_by(
                order_side=OrderSide.SELL.value
            ).count(),
            len(data["items"])
        )

    def test_all_query_params(self):
        portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        query_params = {
            'target_symbol': self.TARGET_SYMBOL_A,
            'trading_symbol': portfolio_manager.trading_symbol,
            'order_side': OrderSide.BUY.value
        }

        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            Order.query.filter_by(
                order_side=OrderSide.BUY.value,
                trading_symbol=portfolio_manager.trading_symbol,
                target_symbol=self.TARGET_SYMBOL_A
            ).count(),
            len(data["items"])
        )

        query_params = {
            'target_symbol': self.TARGET_SYMBOL_A,
            'trading_symbol': portfolio_manager.trading_symbol,
            'order_side': OrderSide.SELL.value
        }

        response = self.client.get("/api/orders", query_string=query_params)
        self.assert200(response)
        data = json.loads(response.data.decode())

        self.assertEqual(
            Order.query.filter_by(
                order_side=OrderSide.SELL.value,
                trading_symbol=portfolio_manager.trading_symbol,
                target_symbol=self.TARGET_SYMBOL_A
            ).count(),
            len(data["items"])
        )
