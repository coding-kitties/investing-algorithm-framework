from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from tests.resources import TestBase


class TestTradeService(TestBase):
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {
        "EUR": 1000
    }

    def test_create_limit_order(self):
        order_repository = self.app.container.order_repository()
        buy_order = order_repository.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 2004,
                "order_side": "BUY",
                "price": 0.24262,
                "order_type": "LIMIT",
                "status": "CREATED",
            }
        )
        trade_service = self.app.container.trade_service()
        trade = trade_service.create_trade_from_buy_order(buy_order)
        self.assertEqual("ADA", trade.target_symbol)
        self.assertEqual("EUR", trade.trading_symbol)
        self.assertEqual(2004, trade.amount)
        self.assertEqual(0.24262, trade.open_price)
        self.assertEqual(1, trade.portfolio_id)
        self.assertIsNotNone(trade.created_at)
        self.assertIsNotNone(trade.closed_at)
        self.assertEqual(2004, trade.remaining)
