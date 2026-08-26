import json

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from tests.resources import WebTestBase
from tests.resources.strategies_for_testing import StrategyOne


class TestRunReportsController(WebTestBase):
    portfolio_configurations = [
        PortfolioConfiguration(market="BITVAVO", trading_symbol="EUR")
    ]
    market_credentials = [
        MarketCredential(market="BITVAVO", api_key="", secret_key="")
    ]
    external_balances = {"EUR": 1000}

    def test_list_run_reports_ordered_by_completion(self):
        self.iaf_app.add_strategy(StrategyOne)
        self.iaf_app.run(number_of_iterations=1)
        self.iaf_app.run(number_of_iterations=1)

        response = self.client.get("/api/run-reports")
        data = json.loads(response.data.decode())

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(data["items"]))
        # Most-recently-completed run report comes first.
        self.assertGreaterEqual(
            data["items"][0]["completed_at"],
            data["items"][1]["completed_at"],
        )

    def test_list_run_reports_pagination(self):
        self.iaf_app.add_strategy(StrategyOne)
        self.iaf_app.run(number_of_iterations=1)
        self.iaf_app.run(number_of_iterations=1)
        self.iaf_app.run(number_of_iterations=1)

        response = self.client.get("/api/run-reports?page=1&per_page=2")
        data = json.loads(response.data.decode())

        self.assertEqual(200, response.status_code)
        self.assertEqual(2, len(data["items"]))
        self.assertEqual(3, data["total"])
        self.assertEqual(1, data["page"])
        self.assertEqual(2, data["per_page"])

        response = self.client.get("/api/run-reports?page=2&per_page=2")
        data = json.loads(response.data.decode())
        self.assertEqual(1, len(data["items"]))
        self.assertEqual(3, data["total"])
