import json
from unittest.mock import patch

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

    def test_manual_invoke_wait_returns_report(self):
        runner = self.iaf_app.container.algorithm_runner()
        report = {"id": 42, "status": "completed", "signals": []}
        with patch.object(runner, "invoke_now", return_value=report) as invoke:
            response = self.client.post(
                "/api/algorithm/invoke?wait=true&timeout=5&strategy_id=alpha")
        self.assertEqual(200, response.status_code)
        self.assertEqual(report, json.loads(response.data.decode())["report"])
        invoke.assert_called_once_with(["alpha"], wait=True, timeout=5.0)

    def test_manual_invoke_timeout_and_invalid_timeout(self):
        runner = self.iaf_app.container.algorithm_runner()
        with patch.object(runner, "invoke_now", side_effect=TimeoutError):
            response = self.client.post("/api/algorithm/invoke?wait=true")
        self.assertEqual(504, response.status_code)
        self.assertTrue(json.loads(response.data.decode())["invoked"])
        with patch.object(runner, "invoke_now") as invoke:
            for timeout in ("0", "-1", "nan", "inf", "invalid"):
                response = self.client.post(
                    f"/api/algorithm/invoke?wait=true&timeout={timeout}")
                self.assertEqual(400, response.status_code)
            invoke.assert_not_called()

    def test_api_exposes_canonical_and_legacy_trace_fields(self):
        from investing_algorithm_framework import DecisionTrace

        self.iaf_app.add_strategy(StrategyOne)
        self.iaf_app.run(number_of_iterations=1)
        service = self.iaf_app.container.run_report_service()
        report = service.create({
            "decision_traces": [DecisionTrace(summary="API trace").to_dict()],
        })
        response = self.client.get("/api/run-reports")
        self.assertEqual(200, response.status_code)
        items = json.loads(response.data.decode())["items"]
        item = next(item for item in items if item["id"] == report.id)
        self.assertEqual(item["decision_traces"], item["score_cards"])
        self.assertEqual("API trace", item["decision_traces"][0]["summary"])
        self.assertEqual(
            1, item["decision_traces"][0]["decision_trace_version"]
        )

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
