from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, TradeStatus
from tests.resources import TestBase


class Test(TestBase):
    market_credentials = [
        MarketCredential(
            market="BINANCE",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BINANCE",
            trading_symbol="EUR"
        )
    ]
    external_balances = {
        "EUR": 1000,
    }

    def test_get_all_with_status(self):
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()
        order = order_service.create(
            {
                "portfolio_id": 1,
                "target_symbol": "BTC",
                "amount": 1,
                "trading_symbol": "EUR",
                "price": 10,
                "order_side": "BUY",
                "order_type": "LIMIT",
                "status": "OPEN",
            }
        )
        trades = trade_service.get_all({"status": TradeStatus.CREATED.value})
        self.assertEqual(1, len(trades))
        trades = trade_service.get_all({"status": TradeStatus.OPEN.value})
        self.assertEqual(0, len(trades))
        order_service.update(order.id, {"filled": 10})
        trades = trade_service.get_all({"status": TradeStatus.CREATED.value})
        self.assertEqual(0, len(trades))
        trades = trade_service.get_all({"status": TradeStatus.OPEN.value})
        self.assertEqual(1, len(trades))
        trades = trade_service.get_all({"status": TradeStatus.CLOSED.value})
        self.assertEqual(0, len(trades))
