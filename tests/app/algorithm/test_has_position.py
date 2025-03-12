from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from tests.resources import TestBase, MarketDataSourceServiceStub


class Test(TestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
            initial_balance=1000,
        )
    ]
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    external_available_symbols = ["BTC/EUR", "DOT/EUR", "ADA/EUR", "ETH/EUR"]
    external_balances = {
        "EUR": 1000,
    }
    market_data_source_service = MarketDataSourceServiceStub()

    def test_has_position(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertTrue(self.app.context.has_position("EUR"))
        self.assertFalse(self.app.context.has_position("BTC"))
        self.assertEqual(1000, trading_symbol_position.get_amount())
        self.assertFalse(self.app.context.position_exists(symbol="BTC"))
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        btc_position = self.app.context.get_position("BTC")
        self.assertIsNotNone(btc_position)
        self.assertTrue(self.app.context.position_exists("BTC"))
        self.assertFalse(self.app.context.has_position("BTC"))
        self.assertEqual(0, btc_position.get_amount())
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        btc_position = self.app.context.get_position("BTC")
        self.assertIsNotNone(btc_position.get_amount())
        self.assertEqual(1, btc_position.get_amount())
        self.assertNotEqual(990, trading_symbol_position.amount)
        self.assertTrue(self.app.context.has_position("BTC"))

    def test_position_exists_with_amount_gt(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(1000, int(trading_symbol_position.get_amount()))
        self.assertFalse(self.app.context.position_exists(symbol="BTC"))
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        self.assertTrue(self.app.context.position_exists("BTC"))
        self.assertFalse(
            self.app.context.position_exists("BTC", amount_gt=0)
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertTrue(
            self.app.context.position_exists("BTC", amount_gt=0)
        )

    def test_position_exists_with_amount_gte(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(1000, int(trading_symbol_position.get_amount()))
        self.assertFalse(self.app.context.position_exists(symbol="BTC"))
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        self.assertTrue(self.app.context.position_exists("BTC"))
        self.assertTrue(
            self.app.context.position_exists("BTC", amount_gte=0)
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertTrue(
            self.app.context.position_exists("BTC", amount_gte=0)
        )

    def test_position_exists_with_amount_lt(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(1000, int(trading_symbol_position.get_amount()))
        self.assertFalse(self.app.context.position_exists(symbol="BTC"))
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        self.assertTrue(self.app.context.position_exists("BTC"))
        self.assertTrue(
            self.app.context.position_exists("BTC", amount_lt=1)
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertFalse(
            self.app.context.position_exists("BTC", amount_lt=1)
        )

    def test_position_exists_with_amount_lte(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(1000, int(trading_symbol_position.get_amount()))
        self.assertFalse(self.app.context.position_exists(symbol="BTC"))
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        self.assertTrue(self.app.context.position_exists("BTC"))
        self.assertTrue(
            self.app.context.position_exists("BTC", amount_lte=1)
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertTrue(
            self.app.context.position_exists("BTC", amount_lte=1)
        )
