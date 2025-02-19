from decimal import Decimal

from investing_algorithm_framework import PortfolioConfiguration, \
    OrderStatus, MarketCredential
from tests.resources import TestBase, MarketDataSourceServiceStub


class Test(TestBase):
    external_balances = {
        "EUR": 1000
    }
    external_available_symbols = ["BTC/EUR"]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="bitvavo",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]
    market_data_source_service = MarketDataSourceServiceStub()

    def test_create_limit_buy_order_with_percentage_of_portfolio(self):
        order = self.app.context.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="BUY",
            amount=20
        )
        self.assertEqual(OrderStatus.OPEN.value, order.status)
        self.assertEqual(Decimal(10), order.get_price())
        self.assertEqual(Decimal(20), order.get_amount())
