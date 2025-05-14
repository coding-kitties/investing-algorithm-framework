from investing_algorithm_framework.infrastructure import SQLPortfolio
from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from tests.resources import TestBase


class TestPortfolioModel(TestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BINANCE",
            trading_symbol="USDT"
        )
    ]
    external_balances = {
        "USDT": 10000
    }
    market_credentials = [
        MarketCredential(
            market="BINANCE",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]

    def test_default(self):
        portfolio = SQLPortfolio(
            trading_symbol="USDT",
            market="BINANCE",
            unallocated=10000,
            initialized=True
        )
        self.assertEqual("BINANCE", portfolio.get_market())
        self.assertEqual("USDT", portfolio.get_trading_symbol())
        self.assertEqual(10000, portfolio.get_unallocated())
        self.assertEqual("BINANCE", portfolio.get_market())
        self.assertEqual("BINANCE", portfolio.get_identifier())
        self.assertEqual(0, portfolio.get_realized())
        self.assertEqual(0, portfolio.get_total_revenue())
        self.assertEqual(0, portfolio.get_total_cost())
        self.assertEqual(0, portfolio.get_total_net_gain())
        self.assertEqual(0, portfolio.get_total_trade_volume())
        self.assertEqual(10000, portfolio.get_net_size())
        self.assertIsNone(portfolio.get_initial_balance())
        self.assertIsNotNone(portfolio.get_created_at())
        self.assertIsNotNone(portfolio.get_updated_at())

    def test_created_by_app(self):
        portfolio = self.app.context.get_portfolio()
        self.assertEqual("BINANCE", portfolio.get_market())
        self.assertEqual("USDT", portfolio.get_trading_symbol())
        self.assertEqual(10000, portfolio.get_unallocated())
        self.assertEqual("BINANCE", portfolio.get_market())
        self.assertEqual("BINANCE", portfolio.get_identifier())
        self.assertEqual(0, portfolio.get_realized())
        self.assertEqual(0, portfolio.get_total_revenue())
        self.assertEqual(0, portfolio.get_total_cost())
        self.assertEqual(0, portfolio.get_total_net_gain())
        self.assertEqual(0, portfolio.get_total_trade_volume())
        self.assertEqual(10000, portfolio.get_net_size())
        self.assertIsNone(portfolio.get_initial_balance())
        self.assertIsNotNone(portfolio.get_created_at())
        self.assertIsNotNone(portfolio.get_updated_at())

    def test_get_trading_symbol(self):
        portfolio = self.app.context.get_portfolio()
        self.assertIsNotNone(portfolio.get_trading_symbol())
