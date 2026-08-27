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

    def test_order_cost_specification_falls_back_to_exchange_default(self):
        response = self.client.get("api/portfolios/order-cost-specification")
        data = json.loads(response.data.decode())
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(data["items"]))
        specification = data["items"][0]
        self.assertEqual("BITVAVO", specification["identifier"])
        self.assertEqual("BITVAVO", specification["market"])
        self.assertEqual("EUR", specification["trading_symbol"])
        self.assertEqual("exchange_default", specification["source"])
        self.assertIsNotNone(specification["fee_percentage"])
        self.assertGreater(specification["fee_percentage"], 0)

    def test_order_cost_specification_uses_configured_fee(self):
        portfolio_configuration_service = self.iaf_app.container \
            .portfolio_configuration_service()
        portfolio_configuration = portfolio_configuration_service.get(
            "BITVAVO"
        )
        portfolio_configuration._fee_percentage = 0.35

        response = self.client.get("api/portfolios/order-cost-specification")
        data = json.loads(response.data.decode())
        specification = data["items"][0]
        self.assertEqual("configured", specification["source"])
        self.assertEqual(0.35, specification["fee_percentage"])
