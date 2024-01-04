import os
from decimal import Decimal

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration
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
        self.app.initialize()

    def test_get_number_of_positions(self):
        trading_symbol_position = self.app.algorithm.get_position("USDT")
        self.assertEqual(1, self.app.algorithm.get_number_of_positions())
        self.assertEqual(Decimal(1000), trading_symbol_position.get_amount())
        self.app.algorithm.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.assertEqual(2, self.app.algorithm.get_number_of_positions())
        self.app.algorithm.create_limit_order(
            target_symbol="DOT",
            amount=1,
            price=10,
            order_side="BUY",
        )
        order_service.check_pending_orders()
        self.assertEqual(3, self.app.algorithm.get_number_of_positions())
        self.app.algorithm.create_limit_order(
            target_symbol="ADA",
            amount=1,
            price=10,
            order_side="BUY",
        )
        self.assertEqual(3, self.app.algorithm.get_number_of_positions())
