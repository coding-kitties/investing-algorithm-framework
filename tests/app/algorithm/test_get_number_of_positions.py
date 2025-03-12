from decimal import Decimal

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
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

    def test_get_number_of_positions(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(1, self.app.context.get_number_of_positions())
        self.assertEqual(Decimal(1000), trading_symbol_position.get_amount())
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertEqual(2, self.app.context.get_number_of_positions())
        self.app.context.create_limit_order(
            target_symbol="DOT",
            amount=1,
            price=10,
            order_side="BUY",
        )
        order_service.check_pending_orders()
        self.assertEqual(3, self.app.context.get_number_of_positions())
        self.app.context.create_limit_order(
            target_symbol="ADA",
            amount=1,
            price=10,
            order_side="BUY",
        )
        self.assertEqual(3, self.app.context.get_number_of_positions())
