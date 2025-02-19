from decimal import Decimal

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
    external_orders = []
    external_balances = {
        "EUR": 1000,
    }
    market_data_source_service = MarketDataSourceServiceStub()

    def test_has_open_buy_orders(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(Decimal(1000), trading_symbol_position.get_amount())
        order = self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        order_service = self.app.container.order_service()
        order = order_service.find({"symbol": "BTC/EUR"})
        position_service = self.app.container.position_service()
        position = position_service.find({"symbol": "BTC"})
        self.assertTrue(self.app.context.has_open_buy_orders("BTC"))
        order_service.check_pending_orders()
        self.assertFalse(self.app.context.has_open_buy_orders("BTC"))
