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
                secret_key="secret_key",
                api_key="api_key"
            )
        )
        self.app.initialize()

    def test_has_position(self):
        self.app.run(number_of_iterations=1)
        trading_symbol_position = self.app.algorithm.get_position("USDT")
        self.assertTrue(self.app.algorithm.has_position("USDT"))
        self.assertFalse(self.app.algorithm.has_position("BTC"))
        self.assertEqual(1000, trading_symbol_position.get_amount())
        self.assertFalse(self.app.algorithm.position_exists(symbol="BTC"))
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        btc_position = self.app.algorithm.get_position("BTC")
        self.assertIsNotNone(btc_position)
        self.assertTrue(self.app.algorithm.position_exists("BTC"))
        self.assertFalse(self.app.algorithm.has_position("BTC"))
        self.assertEqual(0, btc_position.get_amount())
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        btc_position = self.app.algorithm.get_position("BTC")
        self.assertIsNotNone(btc_position.get_amount())
        self.assertEqual(1, btc_position.get_amount())
        self.assertNotEqual(990, trading_symbol_position.amount)
        self.assertTrue(self.app.algorithm.has_position("BTC"))

    def test_position_exists_with_amount_gt(self):
        self.app.run(number_of_iterations=1)
        trading_symbol_position = self.app.algorithm.get_position("USDT")
        self.assertEqual(1000, int(trading_symbol_position.get_amount()))
        self.assertFalse(self.app.algorithm.position_exists(symbol="BTC"))
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        self.assertTrue(self.app.algorithm.position_exists("BTC"))
        self.assertFalse(
            self.app.algorithm.position_exists("BTC", amount_gt=0)
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertTrue(
            self.app.algorithm.position_exists("BTC", amount_gt=0)
        )

    def test_position_exists_with_amount_gte(self):
        self.app.run(number_of_iterations=1)
        trading_symbol_position = self.app.algorithm.get_position("USDT")
        self.assertEqual(1000, int(trading_symbol_position.get_amount()))
        self.assertFalse(self.app.algorithm.position_exists(symbol="BTC"))
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        self.assertTrue(self.app.algorithm.position_exists("BTC"))
        self.assertTrue(
            self.app.algorithm.position_exists("BTC", amount_gte=0)
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertTrue(
            self.app.algorithm.position_exists("BTC", amount_gte=0)
        )

    def test_position_exists_with_amount_lt(self):
        self.app.run(number_of_iterations=1)
        trading_symbol_position = self.app.algorithm.get_position("USDT")
        self.assertEqual(1000, int(trading_symbol_position.get_amount()))
        self.assertFalse(self.app.algorithm.position_exists(symbol="BTC"))
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        self.assertTrue(self.app.algorithm.position_exists("BTC"))
        self.assertTrue(
            self.app.algorithm.position_exists("BTC", amount_lt=1)
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertFalse(
            self.app.algorithm.position_exists("BTC", amount_lt=1)
        )

    def test_position_exists_with_amount_lte(self):
        self.app.run(number_of_iterations=1)
        trading_symbol_position = self.app.algorithm.get_position("USDT")
        self.assertEqual(1000, int(trading_symbol_position.get_amount()))
        self.assertFalse(self.app.algorithm.position_exists(symbol="BTC"))
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        self.assertTrue(self.app.algorithm.position_exists("BTC"))
        self.assertTrue(
            self.app.algorithm.position_exists("BTC", amount_lte=1)
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertTrue(
            self.app.algorithm.position_exists("BTC", amount_lte=1)
        )
