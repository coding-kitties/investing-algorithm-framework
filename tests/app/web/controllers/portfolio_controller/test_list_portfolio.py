import json

from investing_algorithm_framework import MarketCredential, \
    PortfolioConfiguration
from tests.resources import FlaskTestBase


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

    def test_list_portfolios(self):
        self.iaf_app.context.create_limit_order(
            target_symbol="KSM",
            price=10,
            amount=10,
            order_side="BUY"
        )
        order_repository = self.iaf_app.container.order_repository()
        self.iaf_app.run(number_of_iterations=1)
        self.assertEqual(1, order_repository.count())
        response = self.client.get("api/portfolios")
        data = json.loads(response.data.decode())
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(data["items"]))
        self.assertEqual(1, data["items"][0]["orders"])
        self.assertEqual(2, data["items"][0]["positions"])
