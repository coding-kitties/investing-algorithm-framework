from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential

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
    external_available_symbols = ["BTC/EUR", "DOT/EUR", "ADA/EUR", "ETH/EUR"]
    external_balances = {
        "EUR": 1000,
    }

    def test_name_containing_illegal_characters(self):
        with self.assertRaises(Exception) as context:
            self.app.algorithm.name = "v1/v2"

        self.assertTrue(
            "The name of the algorithm can only contain letters and numbers",str(context.exception)
        )
