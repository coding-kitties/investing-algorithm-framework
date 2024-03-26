from decimal import Decimal

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, SYMBOLS, Order
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
    config = {
        SYMBOLS: ["BTC/EUR", "DOT/EUR", "ADA/EUR", "ETH/EUR"]
    }
    external_available_symbols = ["BTC/EUR", "DOT/EUR", "ADA/EUR", "ETH/EUR"]
    external_orders = [
        Order.from_dict(
            {
                "id": "1323",
                "side": "buy",
                "symbol": "BTC/EUR",
                "amount": 10,
                "price": 10.0,
                "status": "CLOSED",
                "order_type": "limit",
                "order_side": "buy",
                "created_at": "2023-08-08T14:40:56.626362Z",
                "filled": 10,
                "remaining": 0,
            },
        ),
        Order.from_dict(
            {
                "id": "132343",
                "order_side": "SELL",
                "symbol": "BTC/EUR",
                "amount": 10,
                "price": 20.0,
                "status": "CLOSED",
                "order_type": "limit",
                "created_at": "2023-08-08T14:40:56.626362Z",
                "filled": 10,
                "remaining": 0,
            },
        ),
        Order.from_dict(
            {
                "id": "14354",
                "side": "buy",
                "symbol": "DOT/EUR",
                "amount": 10,
                "price": 10.0,
                "status": "CLOSED",
                "order_type": "limit",
                "order_side": "buy",
                "created_at": "2023-09-22T14:40:56.626362Z",
                "filled": 10,
                "remaining": 0,
            },
        ),
        Order.from_dict(
            {
                "id": "49394",
                "side": "buy",
                "symbol": "ETH/EUR",
                "amount": 10,
                "price": 10.0,
                "status": "CLOSED",
                "order_type": "limit",
                "order_side": "buy",
                "created_at": "2023-08-08T14:40:56.626362Z",
                "filled": 10,
                "remaining": 0,
            },
        ),
        Order.from_dict(
            {
                "id": "4939424",
                "order_side": "sell",
                "symbol": "ETH/EUR",
                "amount": 10,
                "price": 10.0,
                "status": "OPEN",
                "order_type": "limit",
                "created_at": "2023-08-08T14:40:56.626362Z",
                "filled": 0,
                "remaining": 0,
            },
        ),
        Order.from_dict(
            {
                "id": "493943434",
                "order_side": "sell",
                "symbol": "DOT/EUR",
                "amount": 10,
                "price": 10.0,
                "status": "OPEN",
                "order_type": "limit",
                "created_at": "2023-08-08T14:40:56.626362Z",
                "filled": 0,
                "remaining": 0,
            },
        ),
    ]
    external_balances = {
        "EUR": 1000,
        "BTC": 0,
        "DOT": 0,
        "ETH": 0,
    }

    def test_has_open_buy_orders(self):
        trading_symbol_position = self.app.algorithm.get_position("EUR")
        self.assertEqual(Decimal(1000), trading_symbol_position.get_amount())
        self.assertTrue(self.app.algorithm.position_exists(symbol="BTC"))
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        order_service = self.app.container.order_service()
        self.assertTrue(self.app.algorithm.has_open_buy_orders("BTC"))
        order_service.check_pending_orders()
        self.assertFalse(self.app.algorithm.has_open_buy_orders("BTC"))
