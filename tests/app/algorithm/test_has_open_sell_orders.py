from investing_algorithm_framework import PortfolioConfiguration, MarketCredential
from tests.resources import TestBase


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

    def test_has_open_sell_orders(self):
        trading_symbol_position = self.app.algorithm.get_position("EUR")
        self.assertEqual(1000, trading_symbol_position.get_amount())
        self.assertFalse(self.app.algorithm.position_exists(symbol="BTC"))
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="SELL",
        )
        self.assertTrue(self.app.algorithm.has_open_sell_orders("BTC"))
        order_service.check_pending_orders()
        self.assertFalse(self.app.algorithm.has_open_sell_orders("BTC"))
