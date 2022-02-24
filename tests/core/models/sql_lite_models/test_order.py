from datetime import datetime

from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import db, \
    SQLLiteOrder
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class TestOrderModel(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self) -> None:
        super(TestOrderModel, self).setUp()

        self.start_algorithm()
        self.portfolio_manager = self.algo_app.algorithm.get_portfolio_manager()

        order = self.create_buy_order(
            1,
            self.TARGET_SYMBOL_A,
            self.get_price(self.TARGET_SYMBOL_A, date=datetime.utcnow()).price,
            self.portfolio_manager
        )

        order.reference_id = 10
        order.save(db)
        db.session.commit()

    def tearDown(self) -> None:
        super(TestOrderModel, self).tearDown()

    def test_get_reference_id(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_reference_id())

    def test_get_target_symbol(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_target_symbol())

    def test_get_trading_symbol(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_trading_symbol())

    def test_get_amount_of_trading_symbol(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_amount_trading_symbol())

    def test_get_amount_of_target_symbol(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_amount_target_symbol())

    def test_get_initial_price(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_initial_price())

    def test_get_price(self):
        order = SQLLiteOrder.query.first()
        order.price = 10
        self.assertIsNotNone(order.get_price())

    def test_get_closing_price(self):
        order = SQLLiteOrder.query.first()
        order.closing_price = 10
        self.assertIsNotNone(order.get_closing_price())

    def test_get_status(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_status())

    def test_get_type(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_type())

    def test_get_side(self):
        order = SQLLiteOrder.query.first()
        self.assertIsNotNone(order.get_side())

    def test_from_dict_pending_limit_order_buy(self):
        order = SQLLiteOrder.from_dict(
            {
                "reference_id": 10493,
                "target_symbol": "DOT",
                "trading_symbol": "USDT",
                "amount_target_symbol": 40,
                "status": "PENDING",
                "price": 10,
                "type": "LIMIT",
                "side": "BUY"
            }
        )

        self.assertIsNotNone(order.get_reference_id())
        self.assertIsNotNone(order.get_target_symbol())
        self.assertIsNotNone(order.get_trading_symbol())
        self.assertIsNotNone(order.get_amount_target_symbol())
        self.assertIsNotNone(order.get_amount_trading_symbol())
        self.assertIsNotNone(order.get_status())
        self.assertIsNotNone(order.get_side())
        self.assertIsNotNone(order.get_type())
        self.assertIsNotNone(order.get_price())

    def test_from_dict_successful_limit_order_buy(self):
        order = SQLLiteOrder.from_dict(
            {
                "reference_id": 10493,
                "target_symbol": "DOT",
                "trading_symbol": "USDT",
                "amount_target_symbol": 40,
                "status": "SUCCESS",
                "price": 10,
                "initial_price": 10,
                "type": "LIMIT",
                "side": "BUY"
            }
        )

        self.assertIsNotNone(order.get_reference_id())
        self.assertIsNotNone(order.get_target_symbol())
        self.assertIsNotNone(order.get_trading_symbol())
        self.assertIsNotNone(order.get_amount_target_symbol())
        self.assertIsNotNone(order.get_amount_trading_symbol())
        self.assertIsNotNone(order.get_status())
        self.assertIsNotNone(order.get_side())
        self.assertIsNotNone(order.get_type())
        self.assertIsNotNone(order.get_price())

        with self.assertRaises(OperationalException):
            SQLLiteOrder.from_dict(
                {
                    "reference_id": 10493,
                    "target_symbol": "DOT",
                    "trading_symbol": "USDT",
                    "amount_target_symbol": 40,
                    "status": "SUCCESS",
                    "price": 10,
                    "type": "LIMIT",
                    "side": "BUY"
                }
            )

    def test_from_dict_closed_limit_order_buy(self):
        order = SQLLiteOrder.from_dict(
            {
                "reference_id": 10493,
                "target_symbol": "DOT",
                "trading_symbol": "USDT",
                "amount_target_symbol": 40,
                "status": "CLOSED",
                "initial_price": 10,
                "closing_price": 11,
                "type": "LIMIT",
                "side": "BUY"
            }
        )

        self.assertIsNotNone(order.get_reference_id())
        self.assertIsNotNone(order.get_target_symbol())
        self.assertIsNotNone(order.get_trading_symbol())
        self.assertIsNotNone(order.get_amount_target_symbol())
        self.assertIsNotNone(order.get_amount_trading_symbol())
        self.assertIsNotNone(order.get_status())
        self.assertIsNotNone(order.get_side())
        self.assertIsNotNone(order.get_type())
        self.assertIsNotNone(order.get_closing_price())
        self.assertIsNotNone(order.get_initial_price())

        with self.assertRaises(OperationalException):
            SQLLiteOrder.from_dict(
                {
                    "reference_id": 10493,
                    "target_symbol": "DOT",
                    "trading_symbol": "USDT",
                    "amount_target_symbol": 40,
                    "status": "CLOSED",
                    "price": 10,
                    "initial_price": 10,
                    "type": "LIMIT",
                    "side": "BUY"
                }
            )

    def test_from_dict_pending_limit_order_sell(self):
        order = SQLLiteOrder.from_dict(
            {
                "reference_id": 10493,
                "target_symbol": "DOT",
                "trading_symbol": "USDT",
                "amount_target_symbol": 40,
                "status": "PENDING",
                "price": 10,
                "type": "LIMIT",
                "side": "SELL"
            }
        )

        self.assertIsNotNone(order.get_reference_id())
        self.assertIsNotNone(order.get_target_symbol())
        self.assertIsNotNone(order.get_trading_symbol())
        self.assertIsNotNone(order.get_amount_target_symbol())
        self.assertIsNotNone(order.get_amount_trading_symbol())
        self.assertIsNotNone(order.get_status())
        self.assertIsNotNone(order.get_side())
        self.assertIsNotNone(order.get_type())
        self.assertIsNotNone(order.get_price())

    def test_from_dict_success_limit_order_sell(self):
        order = SQLLiteOrder.from_dict(
            {
                "reference_id": 10493,
                "target_symbol": "DOT",
                "trading_symbol": "USDT",
                "amount_target_symbol": 40,
                "status": "SUCCESS",
                "price": 10,
                "initial_price": 9,
                "type": "LIMIT",
                "side": "SELL"
            }
        )

        self.assertIsNotNone(order.get_reference_id())
        self.assertIsNotNone(order.get_target_symbol())
        self.assertIsNotNone(order.get_trading_symbol())
        self.assertIsNotNone(order.get_amount_target_symbol())
        self.assertIsNotNone(order.get_amount_trading_symbol())
        self.assertIsNotNone(order.get_status())
        self.assertIsNotNone(order.get_side())
        self.assertIsNotNone(order.get_type())
        self.assertIsNotNone(order.get_price())

    def test_from_dict_closed_limit_order_sell(self):
        order = SQLLiteOrder.from_dict(
            {
                "reference_id": 10493,
                "target_symbol": "DOT",
                "trading_symbol": "USDT",
                "amount_target_symbol": 40,
                "status": "CLOSED",
                "closing_price": 10,
                "initial_price": 9,
                "type": "LIMIT",
                "side": "SELL"
            }
        )

        self.assertIsNotNone(order.get_reference_id())
        self.assertIsNotNone(order.get_target_symbol())
        self.assertIsNotNone(order.get_trading_symbol())
        self.assertIsNotNone(order.get_amount_target_symbol())
        self.assertIsNotNone(order.get_amount_trading_symbol())
        self.assertIsNotNone(order.get_status())
        self.assertIsNotNone(order.get_side())
        self.assertIsNotNone(order.get_type())
        self.assertIsNotNone(order.get_price())

    def test_from_dict_pending_market_order_sell(self):
        order = SQLLiteOrder.from_dict(
            {
                "reference_id": 10493,
                "target_symbol": "DOT",
                "trading_symbol": "USDT",
                "amount_target_symbol": 40,
                "status": "PENDING",
                "price": 10,
                "type": "MARKET",
                "side": "SELL"
            }
        )

        self.assertIsNotNone(order.get_reference_id())
        self.assertIsNotNone(order.get_target_symbol())
        self.assertIsNotNone(order.get_trading_symbol())
        self.assertIsNotNone(order.get_amount_target_symbol())
        self.assertIsNone(order.get_amount_trading_symbol())
        self.assertIsNotNone(order.get_status())
        self.assertIsNotNone(order.get_side())
        self.assertIsNotNone(order.get_type())
        self.assertIsNotNone(order.get_price())

    def test_from_dict_success_market_order_sell(self):
        order = SQLLiteOrder.from_dict(
            {
                "reference_id": 10493,
                "target_symbol": "DOT",
                "trading_symbol": "USDT",
                "amount_target_symbol": 40,
                "status": "SUCCESS",
                "price": 10,
                "initial_price": 9,
                "type": "LIMIT",
                "side": "SELL"
            }
        )

        self.assertIsNotNone(order.get_reference_id())
        self.assertIsNotNone(order.get_target_symbol())
        self.assertIsNotNone(order.get_trading_symbol())
        self.assertIsNotNone(order.get_amount_target_symbol())
        self.assertIsNotNone(order.get_amount_trading_symbol())
        self.assertIsNotNone(order.get_status())
        self.assertIsNotNone(order.get_side())
        self.assertIsNotNone(order.get_type())
        self.assertIsNotNone(order.get_price())

    def test_from_dict_closed_market_order_sell(self):
        order = SQLLiteOrder.from_dict(
            {
                "reference_id": 10493,
                "target_symbol": "DOT",
                "trading_symbol": "USDT",
                "amount_target_symbol": 40,
                "status": "CLOSED",
                "closing_price": 10,
                "initial_price": 9,
                "type": "MARKET",
                "side": "SELL"
            }
        )

        self.assertIsNotNone(order.get_reference_id())
        self.assertIsNotNone(order.get_target_symbol())
        self.assertIsNotNone(order.get_trading_symbol())
        self.assertIsNotNone(order.get_amount_target_symbol())
        self.assertIsNotNone(order.get_amount_trading_symbol())
        self.assertIsNotNone(order.get_status())
        self.assertIsNotNone(order.get_side())
        self.assertIsNotNone(order.get_type())
        self.assertIsNotNone(order.get_price())
