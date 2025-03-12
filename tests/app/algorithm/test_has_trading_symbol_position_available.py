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

    def test_has_trading_symbol_available(self):
        self.assertTrue(
            self.app.context.has_trading_symbol_position_available()
        )
        self.assertTrue(
            self.app.context.has_trading_symbol_position_available(
                percentage_of_portfolio=100
            )
        )
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=250,
            order_side="BUY",
        )
        self.assertFalse(
            self.app.context.has_trading_symbol_position_available(
                percentage_of_portfolio=100
            )
        )
        self.assertTrue(
            self.app.context.has_trading_symbol_position_available()
        )
        self.assertTrue(
            self.app.context.has_trading_symbol_position_available(
                percentage_of_portfolio=75
            )
        )
        self.assertTrue(
            self.app.context.has_trading_symbol_position_available(
                amount_gt=700
            )
        )
        self.assertTrue(
            self.app.context.has_trading_symbol_position_available(
                amount_gte=750
            )
        )
        self.app.context.create_limit_order(
            target_symbol="DOT",
            amount=1,
            price=250,
            order_side="BUY",
        )
        self.assertFalse(
            self.app.context.has_trading_symbol_position_available(
                percentage_of_portfolio=75
            )
        )
        self.assertFalse(
            self.app.context.has_trading_symbol_position_available(
                amount_gt=700
            )
        )
        self.assertFalse(
            self.app.context.has_trading_symbol_position_available(
                amount_gte=750
            )
        )
