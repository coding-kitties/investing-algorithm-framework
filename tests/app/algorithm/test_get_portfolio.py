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

    def test_get_portfolio(self):
        portfolio = self.app.context.get_portfolio()
        self.assertEqual(Decimal(1000), portfolio.get_unallocated())
