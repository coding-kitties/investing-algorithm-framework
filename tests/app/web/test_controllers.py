"""
Consolidated tests for web API controllers.

Merged from:
- web/controllers/order_controller/test_list_orders.py
- web/controllers/portfolio_controller/test_list_portfolio.py
- web/controllers/position_controller/test_list_positions.py

All three endpoints use the same BITVAVO/EUR setup.
FlaskTestBase.tearDown already handles database cleanup, so we don't
override it here.
"""
import json

from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from tests.resources import FlaskTestBase
from tests.resources.strategies_for_testing import StrategyOne


class TestWebControllers(FlaskTestBase):
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
    external_balances = {"EUR": 1000}

    def test_list_portfolios(self):
        self.iaf_app.add_strategy(StrategyOne)
        self.iaf_app.run(number_of_iterations=1)
        response = self.client.get("/api/portfolios")
        data = json.loads(response.data.decode())
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(data["items"]))

    def test_list_orders(self):
        self.iaf_app.add_strategy(StrategyOne)
        self.iaf_app.run(number_of_iterations=1)
        response = self.client.get("/api/orders")
        data = json.loads(response.data.decode())
        self.assertEqual(200, response.status_code)

    def test_list_positions(self):
        self.iaf_app.add_strategy(StrategyOne)
        order_repository = self.iaf_app.container.order_repository()
        self.iaf_app.run(number_of_iterations=1)
        self.assertEqual(0, order_repository.count())
        response = self.client.get("/api/positions")
        data = json.loads(response.data.decode())
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(data["items"]))

