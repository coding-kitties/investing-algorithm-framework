from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from investing_algorithm_framework.services import PortfolioService
from tests.resources import TestBase


class TestPortfolioService(TestBase):
    storage_repo_type = "pandas"
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
            initial_balance=1000,
        )
    ]
    external_balances = {
        "EUR": 1000
    }
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]

    def test_create_portfolio_configuration(self):
        portfolio_service: PortfolioService \
            = self.app.container.portfolio_service()

        portfolio = portfolio_service.find({"market": "binance"})
        portfolio_service.create_portfolio_from_configuration(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="EUR",
            )
        )
        self.assertEqual(1000, portfolio.unallocated)

        portfolio_service.create_portfolio_from_configuration(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="EUR",
            )
        )
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(1000, portfolio.unallocated)
