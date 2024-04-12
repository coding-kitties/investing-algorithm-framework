from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, APP_MODE, AppMode, StatelessAction, create_app
from tests.resources import MarketServiceStub
from tests.resources import TestBase


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
        self.app.run(
            number_of_iterations=1,
            payload={"action": StatelessAction.RUN_STRATEGY.value}
        )
        self.assertEqual(1000, self.app.algorithm.get_unallocated())
        trading_symbol_position = self.app.algorithm.get_position(
            symbol="EUR"
        )
        self.assertEqual(1000, trading_symbol_position.get_amount())

    def test_run_with_changed_external_positions(self):
        app = create_app(config={APP_MODE: AppMode.STATELESS.value})
        app.add_algorithm(self.algorithm)
        app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR"
            )
        )
        market_service = MarketServiceStub(None)
        market_service.balances = {
            "EUR": 1000,
            "BTC": 1
        }
        app.container.market_service.override(market_service)
        app.initialize()
        self.assertTrue(AppMode.STATELESS.equals(app.config[APP_MODE]))
        self.app.run(payload={
            "action": StatelessAction.RUN_STRATEGY.value,
        })
        self.assertEqual(1000, app.algorithm.get_unallocated())
        trading_symbol_position = self.app.algorithm.get_position(
            symbol="EUR"
        )
        self.assertEqual(1000, trading_symbol_position.get_amount())
        app = create_app(config={APP_MODE: AppMode.STATELESS.value})
        app.add_algorithm(self.algorithm)
        app.add_market_credential(
            MarketCredential(
                market="BITVAVO",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="BITVAVO",
                trading_symbol="EUR"
            )
        )
        market_service = MarketServiceStub(None)
        market_service.balances = {
            "EUR": 2000,
            "BTC": 1
        }
        app.container.market_service.override(market_service)
        app.initialize()
        self.assertEqual(2000, app.algorithm.get_unallocated())
        trading_symbol_position = self.app.algorithm.get_position(
            symbol="EUR"
        )
        self.assertEqual(2000, trading_symbol_position.get_amount())
