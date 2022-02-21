from investing_algorithm_framework.core.models import Position, Portfolio, \
    Order, OrderStatus, OrderType, OrderSide
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin


class TestPortfolioModel(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(TestPortfolioModel, self).setUp()
        self.portfolio = Portfolio(
            orders=[
                Order(
                    trading_symbol="USDT",
                    target_symbol="DOT",
                    status=OrderStatus.PENDING,
                    price=10,
                    amount_target_symbol=10,
                    order_side=OrderSide.BUY,
                    order_type=OrderType.LIMIT
                )
            ],
            identifier="BINANCE",
            trading_symbol="USDT",
            unallocated_position=Position(amount=10, symbol="USDT", price=10),
            positions=[Position(amount=10, symbol="DOT", price=10)],
            market="BINANCE"
        )

    def test_get_trading_symbol(self):
        self.assertIsNotNone(self.portfolio.get_trading_symbol())

    def test_get_unallocated(self):
        self.assertIsNotNone(self.portfolio.get_unallocated())
        self.assertIsNotNone(self.portfolio.get_unallocated().amount)
        self.assertTrue(
            isinstance(self.portfolio.get_unallocated(), Position)
        )

    def test_get_allocated(self):
        self.assertIsNotNone(self.portfolio.get_allocated())
        self.assertNotEqual(0, self.portfolio.get_allocated())

    def test_get_id(self):
        self.assertIsNotNone(self.portfolio.get_identifier())

    def test_get_orders(self):
        self.assertIsNotNone(self.portfolio.get_orders())
        self.assertNotEqual(0, len(self.portfolio.get_orders()))

    def test_get_positions(self):
        self.assertIsNotNone(self.portfolio.get_positions())
        self.assertNotEqual(0, len(self.portfolio.get_positions()))

    def test_get_total_revenue(self):
        self.assertIsNotNone(self.portfolio.get_total_revenue())
        self.assertEqual(0, self.portfolio.get_total_revenue())

    def test_get_market(self):
        self.assertIsNotNone(self.portfolio.get_market())
        self.assertEqual("BINANCE", self.portfolio.get_market())
