from datetime import datetime
from unittest import TestCase

from investing_algorithm_framework.domain import PortfolioConfiguration


class Test(TestCase):

    def test_portfolio_configuration(self):
        portfolio_configuration = PortfolioConfiguration(
            track_from="01/01/2022",
            trading_symbol="USDT",
            identifier="test",
            market="BINANCE",
            initial_balance=400
        )
        self.assertIsNotNone(portfolio_configuration.trading_symbol)
        self.assertIsNotNone(portfolio_configuration.identifier)
        self.assertIsNotNone(portfolio_configuration.market)
        self.assertIsNotNone(portfolio_configuration.track_from)
        self.assertIsNotNone(portfolio_configuration.track_from)
        self.assertIsInstance(portfolio_configuration.track_from, datetime)
        self.assertEqual(portfolio_configuration.initial_balance, 400)
