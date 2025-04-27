import os
from unittest import TestCase

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY


class Test(TestCase):

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.realpath(__file__),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )

    def test_add(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(
            market="binance", trading_symbol="EUR",
        )

        # Check that a binance portfolio configuration was created
        portfolio_configurations = app.get_portfolio_configurations()
        self.assertEqual(len(portfolio_configurations), 1)
        self.assertEqual(
            portfolio_configurations[0].market, "BINANCE"
        )
        self.assertEqual(
            portfolio_configurations[0].trading_symbol, "EUR"
        )
        self.assertIsNone(
            portfolio_configurations[0].initial_balance
        )

        # Check that a binance market credential was created
        market_credentials = app.get_market_credentials()
        self.assertEqual(len(market_credentials), 1)

    def test_add_with_api_key(self):
        app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        app.add_market(
            market="binance",
            trading_symbol="EUR",
            api_key="api_key",
            secret_key="secret_key"
        )

        potfolio_configurations = app.get_portfolio_configurations()[0]
        self.assertEqual(
            potfolio_configurations.market, "BINANCE"
        )
        self.assertEqual(
            potfolio_configurations.trading_symbol, "EUR"
        )
        self.assertIsNone(
            potfolio_configurations.initial_balance
        )

        market_credential = app.get_market_credentials()[0]
        self.assertEqual(
            market_credential.market, "BINANCE"
        )
        self.assertEqual(
            market_credential.api_key, "api_key"
        )
        self.assertEqual(
            market_credential.secret_key, "secret_key"
        )
