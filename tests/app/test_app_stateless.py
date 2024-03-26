from tests.resources import TestBase
from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, APP_MODE, AppMode, StatelessAction


class Test(TestBase):
    config = {
        APP_MODE: "stateless"
    }
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="BITVAVO",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]
    external_balances = {
        "EUR": 1000,
    }

    def test_run(self):
        config = self.app.config
        self.assertTrue(AppMode.STATELESS.equals(config[APP_MODE]))
        self.app.run(number_of_iterations=1)
        self.assertEqual(1000, self.app.algorithm.get_unallocated())
        trading_symbol_position = self.app.algorithm.get_position(
            symbol="EUR"
        )
        self.assertEqual(1000, trading_symbol_position.get_amount())

    def test_run_with_changed_external_positions(self):
        config = self.app.config
        self.assertTrue(AppMode.STATELESS.equals(config[APP_MODE]))
        self.app.run(payload={
            "action": StatelessAction.RUN_STRATEGY.value,
        })
        self.assertEqual(1000, self.app.algorithm.get_unallocated())
        trading_symbol_position = self.app.algorithm.get_position(
            symbol="EUR"
        )
        self.assertEqual(1000, trading_symbol_position.get_amount())
        self.market_service.external_balances = {
            "EUR": 2000,
            "BTC": 1
        }
        self.app.container.market_service.override(self.market_service)
        self.app.run(payload={
            "action": StatelessAction.RUN_STRATEGY.value,
        })
        self.assertEqual(2000, trading_symbol_position.get_amount())
