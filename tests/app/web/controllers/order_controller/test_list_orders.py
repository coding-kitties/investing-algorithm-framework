import json
import os
import shutil

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from tests.resources import FlaskTestBase
from tests.resources.strategies_for_testing import StrategyOne


class Test(FlaskTestBase):
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

    def test_list_portfolios(self):
        self.iaf_app.add_strategy(StrategyOne)
        self.iaf_app.run(number_of_iterations=1)
        response = self.client.get("/api/portfolios")
        data = json.loads(response.data.decode())
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(data["items"]))
