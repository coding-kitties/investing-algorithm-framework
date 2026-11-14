from datetime import datetime, timedelta

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, TradeStatus
from investing_algorithm_framework.infrastructure.database import Session
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

    def test_trade_orders_reload_in_chronological_order(self):
        order_service = self.app.container.order_service()
        trade_service = self.app.container.trade_service()
        start = datetime(2023, 1, 1)
        orders = []
        for offset in (2, 0, 1):
            order = order_service.create({
                "portfolio_id": 1, "target_symbol": "BTC", "amount": 1,
                "trading_symbol": "EUR", "price": 10,
                "order_side": "BUY", "order_type": "LIMIT",
                "status": "OPEN", "created_at": start + timedelta(days=offset),
            })
            order_service.update(order.id, {
                "filled": 1, "remaining": 0, "status": "CLOSED",
            })
            orders.append(order)
        trade = trade_service.get_all({"status": TradeStatus.OPEN.value})[0]
        trade.orders = orders
        expected = [
            order.id
            for order in sorted(orders, key=lambda item: item.created_at)
        ]
        with Session() as session:
            trade = session.merge(trade)
            session.flush()
            session.expire(trade, ['orders'])
            self.assertEqual(expected, [order.id for order in trade.orders])

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
        # v9.0 (#431) — no trade exists until the order fills.
        trades = trade_service.get_all({"status": TradeStatus.OPEN.value})
        self.assertEqual(0, len(trades))
        order_service.update(order.id, {"filled": 1, "remaining": 0,
                                        "status": "CLOSED"})
        trades = trade_service.get_all({"status": TradeStatus.OPEN.value})
        self.assertEqual(1, len(trades))
        trades = trade_service.get_all({"status": TradeStatus.CLOSED.value})
        self.assertEqual(0, len(trades))
