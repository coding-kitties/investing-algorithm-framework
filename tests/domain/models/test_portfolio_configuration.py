from datetime import datetime
from unittest import TestCase
from unittest.mock import patch

from investing_algorithm_framework import PositionMode, PaperTradingMode
from investing_algorithm_framework.domain import PortfolioConfiguration, \
    ImproperlyConfigured


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

    def test_position_mode_defaults_to_netting(self):
        configuration = PortfolioConfiguration(
            market="BITVAVO", trading_symbol="EUR"
        )

        self.assertEqual(PositionMode.NETTING, configuration.position_mode)

    def test_hedge_position_mode_round_trip(self):
        configuration = PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR",
            position_mode=PositionMode.HEDGE,
        )

        restored = PortfolioConfiguration.from_dict(configuration.to_dict())

        self.assertEqual(configuration, restored)
        self.assertEqual(PositionMode.HEDGE, restored.position_mode)
        self.assertEqual("hedge", configuration.to_dict()["position_mode"])

    def test_old_configuration_payload_defaults_to_netting(self):
        restored = PortfolioConfiguration.from_dict({
            "market": "BITVAVO",
            "trading_symbol": "EUR",
        })

        self.assertEqual(PositionMode.NETTING, restored.position_mode)

    def test_paper_trading_defaults_to_disabled(self):
        configuration = PortfolioConfiguration(
            market="BITVAVO", trading_symbol="EUR"
        )

        self.assertFalse(configuration.paper_trading)
        self.assertEqual(
            PaperTradingMode.AUTO, configuration.paper_trading_mode
        )

    def test_paper_trading_requires_initial_balance(self):
        with self.assertRaisesRegex(
            ImproperlyConfigured, "requires an initial_balance"
        ):
            PortfolioConfiguration(
                market="BITVAVO", trading_symbol="EUR", paper_trading=True,
            )

    def test_paper_trading_round_trip(self):
        configuration = PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR",
            initial_balance=1000,
            paper_trading=True,
            paper_trading_mode=PaperTradingMode.LOCAL,
        )

        restored = PortfolioConfiguration.from_dict(configuration.to_dict())

        self.assertEqual(configuration, restored)
        self.assertTrue(restored.paper_trading)
        self.assertEqual(PaperTradingMode.LOCAL, restored.paper_trading_mode)

    def test_market_falls_back_to_environment_variable(self):
        with patch.dict(
            "os.environ", {"MARKET": "BITVAVO"}, clear=False
        ):
            configuration = PortfolioConfiguration(trading_symbol="EUR")

        self.assertEqual("BITVAVO", configuration.market)

    def test_trading_symbol_falls_back_to_environment_variable(self):
        with patch.dict(
            "os.environ", {"TRADING_SYMBOL": "eur"}, clear=False
        ):
            configuration = PortfolioConfiguration(market="BITVAVO")

        self.assertEqual("EUR", configuration.trading_symbol)

    def test_initial_balance_falls_back_to_environment_variable(self):
        with patch.dict(
            "os.environ", {"INITIAL_BALANCE": "2500"}, clear=False
        ):
            configuration = PortfolioConfiguration(
                market="BITVAVO", trading_symbol="EUR"
            )

        self.assertEqual(2500.0, configuration.initial_balance)

    def test_invalid_initial_balance_environment_variable_raises(self):
        with patch.dict(
            "os.environ", {"INITIAL_BALANCE": "not-a-number"}, clear=False
        ):
            with self.assertRaisesRegex(
                ImproperlyConfigured, "not a valid number"
            ):
                PortfolioConfiguration(
                    market="BITVAVO", trading_symbol="EUR"
                )

    def test_missing_market_raises_with_no_env_var(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(
                ImproperlyConfigured, "requires a market"
            ):
                PortfolioConfiguration(trading_symbol="EUR")

    def test_missing_trading_symbol_raises_with_no_env_var(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(
                ImproperlyConfigured, "requires a trading symbol"
            ):
                PortfolioConfiguration(market="BITVAVO")
