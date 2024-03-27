from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from investing_algorithm_framework.services import PortfolioService
from tests.resources import MarketServiceStub
from tests.resources import TestBase


class TestPortfolioService(TestBase):
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

        market_service_stub = MarketServiceStub(None)
        market_service_stub.balances = {
            "EUR": 1000,
            "BTC": 20,
        }
        portfolio_service.market_service = market_service_stub
        portfolio = portfolio_service.find({"market": "binance"})
        portfolio_service.create_portfolio_from_configuration(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="EUR",
            )
        )
        self.assertEqual(1000, portfolio.unallocated)

        # Test when a new sync is ma de the unallocated is not updated
        # Because it already exists
        market_service_stub.balances = {
            "EUR": 2000,
            "BTC": 30,
        }
        portfolio_service.create_portfolio_from_configuration(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="EUR",
            )
        )
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(1000, portfolio.unallocated)
