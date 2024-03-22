import json

from investing_algorithm_framework import PortfolioConfiguration
from tests.resources import FlaskTestBase


class Test(FlaskTestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="USDT"
        )
    ]

    def setUp(self) -> None:
        super(Test, self).setUp()

    def test_list_portfolios(self):
        order_repository = self.iaf_app.container.order_repository()
        self.iaf_app.run(number_of_iterations=1)
        self.assertEqual(1, order_repository.count())
        response = self.client.get("/api/orders")
        data = json.loads(response.data.decode())
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(data["items"]))
