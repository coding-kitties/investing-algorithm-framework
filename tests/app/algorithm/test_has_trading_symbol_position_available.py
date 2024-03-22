import os

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration, Algorithm, MarketCredential
from tests.resources import TestBase, MarketServiceStub


class Test(TestBase):

    def setUp(self) -> None:
        self.resource_dir = os.path.abspath(
            os.path.join(
                os.path.join(
                    os.path.join(
                        os.path.join(
                            os.path.realpath(__file__),
                            os.pardir
                        ),
                        os.pardir
                    ),
                    os.pardir
                ),
                "resources"
            )
        )
        self.app = create_app(config={RESOURCE_DIRECTORY: self.resource_dir})
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="USDT"
            )
        )
        self.app.container.market_service.override(MarketServiceStub(None))
        self.app.add_algorithm(Algorithm())
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="api_key",
                secret_key="secret_key"
            )
        )
        self.app.initialize()

    def test_has_trading_symbol_available(self):
        self.assertTrue(
            self.app.algorithm.has_trading_symbol_position_available()
        )
        self.assertTrue(
            self.app.algorithm.has_trading_symbol_position_available(
                percentage_of_portfolio=100
            )
        )
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=250,
            order_side="BUY",
        )
        self.assertFalse(
            self.app.algorithm.has_trading_symbol_position_available(
                percentage_of_portfolio=100
            )
        )
        self.assertTrue(
            self.app.algorithm.has_trading_symbol_position_available()
        )
        self.assertTrue(
            self.app.algorithm.has_trading_symbol_position_available(
                percentage_of_portfolio=75
            )
        )
        self.assertTrue(
            self.app.algorithm.has_trading_symbol_position_available(
                amount_gt=700
            )
        )
        self.assertTrue(
            self.app.algorithm.has_trading_symbol_position_available(
                amount_gte=750
            )
        )
        self.app.algorithm.create_limit_order(
            target_symbol="DOT",
            amount=1,
            price=250,
            order_side="BUY",
        )
        self.assertFalse(
            self.app.algorithm.has_trading_symbol_position_available(
                percentage_of_portfolio=75
            )
        )
        self.assertFalse(
            self.app.algorithm.has_trading_symbol_position_available(
                amount_gt=700
            )
        )
        self.assertFalse(
            self.app.algorithm.has_trading_symbol_position_available(
                amount_gte=750
            )
        )
