from investing_algorithm_framework import \
    PortfolioConfiguration, MarketCredential
from investing_algorithm_framework.infrastructure.models import SQLOrder
from tests.resources import TestBase


class Test(TestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="USDT"
        )
    ]
    external_balances = {
       "USDT": 1000
    }
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]

    def test_creation(self):
        order = SQLOrder(
            amount=2004.5303357979318,
            price=0.2431,
            order_side="BUY",
            order_type="LIMIT",
            status="OPEN",
            target_symbol="ADA",
            trading_symbol="USDT",
        )
        self.assertEqual(order.amount, 2004.5303357979318)
        self.assertEqual(order.get_amount(), 2004.5303357979318)
        self.assertEqual(order.price, 0.2431)
        self.assertEqual(order.get_price(), 0.2431)
