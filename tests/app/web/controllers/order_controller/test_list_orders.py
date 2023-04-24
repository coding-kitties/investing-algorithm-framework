import requests
import json

from investing_algorithm_framework import TradingStrategy, \
    TimeUnit, PortfolioConfiguration, OrderStatus
from tests.resources import FlaskTestBase


class StrategyOne(TradingStrategy):
    time_unit = TimeUnit.SECOND
    interval = 1

    def apply_strategy(
        self,
        algorithm,
        market_data,
    ):
        algorithm.create_order(
            target_symbol="BTC",
            amount_target_symbol=1,
            price=10,
            side="BUY",
            type="LIMIT",
        )


class Test(FlaskTestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            api_key="test",
            secret_key="test",
            trading_symbol="USDT"
        )
    ]

    def test_list_orders(self):
        order_repository = self.iaf_app.container.order_repository()
        order_service = self.iaf_app.container.order_service()
        self.iaf_app.algorithm.create_order(
            target_symbol="BTC",
            amount_target_symbol=1,
            price=10,
            side="BUY",
            type="LIMIT",
            market="BITVAVO",
        )
        self.iaf_app.run(number_of_iterations=1, sync=False)
        self.assertEqual(1, order_repository.count())
        response = self.client.get(f'/api/orders')
        data = json.loads(response.data.decode())
        self.assertEqual(200, response.status_code)
        self.assertTrue(
            OrderStatus.PENDING.equals(data["items"][0]["status"])
        )
        order_service.check_pending_orders()
        response = self.client.get(f'/api/orders')
        self.assertEqual(200, response.status_code)
        data = json.loads(response.data.decode())
        self.assertTrue(
            OrderStatus.SUCCESS.equals(data["items"][0]["status"])
        )
