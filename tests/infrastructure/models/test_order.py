import os

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration
from investing_algorithm_framework.infrastructure.models import SQLOrder
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
                api_key="test",
                secret_key="test",
                trading_symbol="USDT"
            )
        )
        self.app.container.market_service.override(MarketServiceStub())
        self.app.initialize()

    def test_creation(self):
        order = SQLOrder(
            amount=2004.5303357979318,
            price=0.2431,
            order_side="BUY",
            order_type="LIMIT",
            status="OPEN",
            target_symbol="ADA",
            trading_symbol="USDT",
        )
        self.assertEqual(order.amount, 2004.5303357979318)
        self.assertEqual(order.get_amount(), 2004.5303357979318)
        self.assertEqual(order.price, 0.2431)
        self.assertEqual(order.get_price(), 0.2431)
