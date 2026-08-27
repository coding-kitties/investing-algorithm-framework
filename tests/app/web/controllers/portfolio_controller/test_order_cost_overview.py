import json
import os
import shutil

from investing_algorithm_framework import MarketCredential, \
    PortfolioConfiguration
from tests.resources import WebTestBase


class Test(WebTestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="BITVAVO",
            api_key="",
            secret_key=""
        )
    ]
    external_balances = {
        "EUR": 1000
    }

    def tearDown(self) -> None:
        super().tearDown()

        database_dir = os.path.join(
            self.resource_directory, "databases"
        )

        if os.path.exists(database_dir):
            shutil.rmtree(database_dir, ignore_errors=True)

    def test_order_cost_overview(self):
        order_service = self.iaf_app.container.order_service()
        first_order = order_service.create(
            {
                "target_symbol": "DOT",
                "trading_symbol": "EUR",
                "amount": 10,
                "order_side": "BUY",
                "price": 10,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        order_service.update(
            first_order.id,
            {
                "status": "CLOSED",
                "filled": 10,
                "remaining": 0,
                "order_fee": 1.5,
                "slippage": 0.02,
            }
        )
        second_order = order_service.create(
            {
                "target_symbol": "DOT",
                "trading_symbol": "EUR",
                "amount": 5,
                "order_side": "BUY",
                "price": 10,
                "order_type": "LIMIT",
                "portfolio_id": 1,
                "status": "CREATED",
            }
        )
        order_service.update(
            second_order.id,
            {
                "order_fee": 0.75,
                "slippage": 0.01,
            }
        )

        response = self.client.get("api/portfolios/order-costs")
        data = json.loads(response.data.decode())
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(data["items"]))
        overview = data["items"][0]
        self.assertEqual("BITVAVO", overview["identifier"])
        self.assertEqual("BITVAVO", overview["market"])
        self.assertEqual("EUR", overview["trading_symbol"])
        self.assertEqual(2, overview["number_of_orders"])
        self.assertEqual(1, overview["number_of_filled_orders"])
        self.assertAlmostEqual(2.25, overview["total_order_fee"])
        self.assertAlmostEqual(0.03, overview["total_slippage"])

    def test_order_cost_overview_filters_by_identifier(self):
        response = self.client.get(
            "api/portfolios/order-costs?identifier=OTHER"
        )
        data = json.loads(response.data.decode())
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, len(data["items"]))
