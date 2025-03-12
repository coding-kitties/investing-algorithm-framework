from investing_algorithm_framework import PortfolioConfiguration, Algorithm, \
    MarketCredential, OperationalException, RESERVED_BALANCES
from tests.resources import TestBase


class Test(TestBase):
    initialize = False

    def test_sync_unallocated(self):
        """
        Test the sync_unallocated method of the PortfolioSyncService class.

        1. Create a PortfolioSyncService object.
        2. Create a portfolio with 1000 unallocated balance.
        3. Check if the portfolio still has the 1000 eu after the
        sync_unallocated method is called.
        """
        portfolio_sync_service = self.app.container.portfolio_sync_service()
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {"EUR": 1000}
        self.app.add_algorithm(Algorithm())
        self.app.initialize_config()
        self.app.initialize()
        portfolio = self.app.container.portfolio_service()\
            .find({"identifier": "test"})
        self.assertEqual(1000, portfolio.unallocated)

        # Sync again but with the new balance, if not stateless the
        # unallocated balance should be the same
        self.market_service.balances = {"EUR": 2000}
        portfolio_sync_service.sync_unallocated(portfolio)
        self.assertEqual(1000, portfolio.unallocated)

    def test_sync_unallocated_with_no_balance(self):
        """
        Test the sync_unallocated method of the PortfolioSyncService class.

        1. Create a PortfolioSyncService object.
        2. Create a portfolio with 1000 unallocated balance.
        3. Check if the portfolio still has the 1000 eu after the
        sync_unallocated method is called.
        """
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {"EUR": 0}
        self.app.add_algorithm(Algorithm())

        with self.assertRaises(OperationalException) as context:
            self.app.initialize_config()
            self.app.initialize()

        self.assertEqual(
            "The initial balance of the portfolio configuration (1000.0 EUR) is more than the available balance on the exchange. Please make sure that the initial balance of the portfolio configuration is less than the available balance on the exchange 0.0 EUR.",
            str(context.exception)
        )

    def test_sync_unallocated_with_reserved(self):
        configuration_service = self.app.container.configuration_service()
        configuration_service.config[RESERVED_BALANCES] = {"EUR": 500}
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=500
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {"EUR": 1200}
        self.app.add_algorithm(Algorithm())
        self.app.initialize_config()
        self.app.initialize()

        portfolio = self.app.container.portfolio_service() \
            .find({"identifier": "test"})
        self.assertEqual(500, portfolio.unallocated)

    def test_sync_unallocated_with_initial_size(self):
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=500
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {"EUR": 1200}
        self.app.add_algorithm(Algorithm())
        self.app.initialize_config()
        self.app.initialize()

        portfolio = self.app.container.portfolio_service() \
            .find({"identifier": "test"})
        self.assertEqual(500, portfolio.unallocated)
