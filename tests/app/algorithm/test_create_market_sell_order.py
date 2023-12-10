import os

from investing_algorithm_framework import create_app, RESOURCE_DIRECTORY, \
    PortfolioConfiguration, OrderType, OrderSide, \
    OrderStatus
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
                market="BITVAVO",
                api_key="test",
                secret_key="test",
                trading_symbol="EUR"
            )
        )
        self.app.container.market_service.override(MarketServiceStub())
        self.app.initialize()
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "BITVAVO"})
        order_service = self.app.container.order_service()
        order_service.create(
            {
                "target_symbol": "BTC",
                "price": 10,
                "amount": 1,
                "order_type": OrderType.LIMIT.value,
                "order_side": OrderSide.BUY.value,
                "portfolio_id": portfolio.id,
                "status": OrderStatus.CREATED.value,
                "trading_symbol": portfolio.trading_symbol,
            },
        )
        order_service.check_pending_orders()

    def test_create_market_sell_order(self):
        position_service = self.app.container.position_service()
        order_service = self.app.container.order_service()
        trading_symbol_position = position_service.find({"symbol": "EUR"})
        self.assertEqual(990, trading_symbol_position.get_amount())
        self.app.run(number_of_iterations=1, sync=False)
        trading_symbol_position = position_service.find({"symbol": "EUR"})
        self.assertEqual(990, trading_symbol_position.get_amount())
        self.app.algorithm.create_market_order(
            target_symbol="BTC",
            amount=1,
            order_side="SELL",
        )
        btc_position = position_service.find({"symbol": "BTC"})
        self.assertEqual(0, btc_position.get_amount())
        order_service.check_pending_orders()
        btc_position = position_service.find({"symbol": "BTC"})
        trading_symbol_position = position_service.find({"symbol": "EUR"})
        self.assertEqual(0, btc_position.get_amount())
        self.assertEqual(990, trading_symbol_position.get_amount())
