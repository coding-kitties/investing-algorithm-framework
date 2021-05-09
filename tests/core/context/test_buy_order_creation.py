from tests.resources import TestBase
from investing_algorithm_framework.core.models import Order, OrderType, \
    Position
from investing_algorithm_framework.core.exceptions import OperationalException


class TestOrderModel(TestBase):

    def setUp(self) -> None:
        super(TestOrderModel, self).setUp()
        self.algorithm_context.add_data_provider(self.data_provider)
        self.algorithm_context.add_portfolio_manager(self.portfolio_manager)
        self.algorithm_context.add_order_executor(self.order_executor)

    def test_order_creation(self):
        self.algorithm_context.perform_limit_order(
            broker="BINANCE",
            trading_pair="BTC/USDT",
            amount=10.3,
            price=10.40,
            order_type=OrderType.BUY
        )

        self.assertEqual(
            1, Order.query.filter_by(order_type=OrderType.BUY.value).count()
        )
        self.assertEqual(1, Position.query.count())
        self.assertEqual(1, Position.query.filter_by(symbol="BTC").count())

        self.algorithm_context.perform_limit_order(
            broker="BINANCE",
            trading_pair="BTC-USDT",
            amount=10.3,
            price=10.40,
            order_type=OrderType.BUY
        )

        self.assertEqual(
            2, Order.query.filter_by(order_type=OrderType.BUY.value).count()
        )

        position = Position.query.filter_by(symbol="BTC").first()

        self.assertEqual(
            2, Order.query.filter_by(order_type=OrderType.BUY.value).count()
        )
        self.assertEqual(
            2, Order.query.filter_by(position=position).count()
        )
        self.assertEqual(1, Position.query.count())
        self.assertEqual(1, Position.query.filter_by(symbol="BTC").count())
        self.assertEqual(2, Order.query.filter_by(completed=True).count())

    def test_order_creation_that_exceeds_free_space(self):

        with self.assertRaises(OperationalException) as exception_info:
            self.algorithm_context.perform_limit_order(
                broker="BINANCE",
                trading_pair="BTC/USDT",
                amount=60,
                price=10,
                order_type=OrderType.BUY
            )

        self.assertEqual(
            "Request order size exceeds free portfolio size",
            exception_info.exception.error_message
        )

        self.assertEqual(
            0, Order.query.filter_by(order_type=OrderType.BUY.value).count()
        )

        self.assertEqual(0, Position.query.filter_by(symbol="BTC").count())
        self.assertEqual(0, Order.query.filter_by(completed=True).count())

    def test_order_creation_without_matching_portfolio_manager(self):
        with self.assertRaises(OperationalException) as exception_info:
            self.algorithm_context.perform_limit_order(
                broker="KRAKEN",
                trading_pair="BTC/USDT",
                amount=60,
                price=10,
                order_type=OrderType.BUY
            )

        self.assertEqual(
            "There is no portfolio manager linked to the given broker",
            exception_info.exception.error_message
        )

        self.assertEqual(
            0, Order.query.filter_by(order_type=OrderType.BUY.value).count()
        )
        self.assertEqual(0, Position.query.filter_by(symbol="BTC").count())
        self.assertEqual(0, Order.query.filter_by(completed=True).count())
