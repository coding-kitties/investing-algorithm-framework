import json
import os

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
            for root, dirs, files in os.walk(database_dir, topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))

            os.rmdir(database_dir)

    def test_list_portfolios(self):
        self.iaf_app.add_strategy(StrategyOne)
        order_repository = self.iaf_app.container.order_repository()
        self.iaf_app.run(number_of_iterations=1)
        self.assertEqual(0, order_repository.count())
        response = self.client.get("/api/positions")
        data = json.loads(response.data.decode())
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(data["items"]))
