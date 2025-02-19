from decimal import Decimal

from investing_algorithm_framework import PortfolioConfiguration, \
    OrderStatus, MarketCredential
from tests.resources import TestBase, MarketDataSourceServiceStub


class Test(TestBase):
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
    market_data_source_service = MarketDataSourceServiceStub()

    def test_check_order_status(self):
        order_repository = self.app.container.order_repository()
        position_repository = self.app.container.position_repository()
        self.app.context.create_limit_order(
            target_symbol="BTC",
            amount=1,
            price=10,
            order_side="BUY",
        )
        self.assertEqual(1, order_repository.count())
        self.assertEqual(2, position_repository.count())
        self.app.context.order_service.check_pending_orders()
        self.assertEqual(1, order_repository.count())
        self.assertEqual(2, position_repository.count())
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.CLOSED.value, order.status)
        position = position_repository.find({"symbol": "BTC"})
        self.assertEqual(Decimal(1), position.get_amount())
