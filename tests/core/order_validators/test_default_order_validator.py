from investing_algorithm_framework.core.models import db, \
    Portfolio
from investing_algorithm_framework.core.order_validators \
    import OrderValidatorFactory
from tests.resources import TestBase, TestOrderAndPositionsObjectsMixin
from investing_algorithm_framework.core.exceptions import OperationalException
from investing_algorithm_framework.core.models import Order, OrderType


class Test(TestBase, TestOrderAndPositionsObjectsMixin):

    def setUp(self):
        super(Test, self).setUp()
        self.portfolio = Portfolio(
            trading_currency="USDT",
            identifier="BINANCE",
            unallocated=1000
        )
        self.portfolio.save(db)

    def test_validate_limit_buy_order(self):
        order = self.portfolio.create_buy_order(
            "BTC", 20, 20,
        )

        order_validator = OrderValidatorFactory.of("test")
        order_validator.validate(order, self.portfolio)

    def test_validate_limit_sell_order(self):
        portfolio = Portfolio.query.first()
        self.create_buy_orders(2, self.TICKERS, portfolio)

        order = portfolio.create_sell_order(
            self.TICKERS[0], 2, 2,
        )

        portfolio = Portfolio.query.first()
        order_validator = OrderValidatorFactory.of("test")
        order_validator.validate(order, portfolio)

    def test_validate_limit_sell_order_larger_then_position(self):
        portfolio = Portfolio.query.first()
        self.create_buy_orders(2, self.TICKERS, portfolio)

        order = portfolio.create_sell_order(
            self.TICKERS[0], 200, 2,
        )

        portfolio = Portfolio.query.first()
        order_validator = OrderValidatorFactory.of("test")

        with self.assertRaises(OperationalException):
            order_validator.validate(order, portfolio)

    def test_validate_buy_order_with_wrong_trading_symbol(self):
        order = Order(
            "BUY", "LIMIT",
            "BTC", "TEST", 20, 20,
        )
        order_validator = OrderValidatorFactory.of("test")

        with self.assertRaises(OperationalException):
            order_validator.validate(order, self.portfolio)

    def test_validate_limit_order_with_unallocated_error(self):
        order = self.portfolio.create_buy_order(
            "BTC", 200, 20,
        )

        order_validator = OrderValidatorFactory.of("test")

        with self.assertRaises(OperationalException):
            order_validator.validate(order, self.portfolio)

    def test_validate_market_order(self):
        order = self.portfolio.create_buy_order(
            "BTC", 200, 20, order_type=OrderType.MARKET.value
        )

        order_validator = OrderValidatorFactory.of("test")
        order_validator.validate(order, self.portfolio)

    def test_validate_market_order_with_order_amount_is_none(self):
        pass
