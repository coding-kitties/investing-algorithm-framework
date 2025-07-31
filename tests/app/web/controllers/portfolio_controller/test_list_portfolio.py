import json

from investing_algorithm_framework import MarketCredential, \
    PortfolioConfiguration, DataSource, INDEX_DATETIME
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

    def test_list_portfolios(self):
        strategy = StrategyOne()
        strategy.data_sources =[
            DataSource(
                market="BITVAVO",
                symbol="DOT/EUR",
                time_frame="2h",
            )
        ]
        self.iaf_app.add_strategy(StrategyOne)
        order_repository = self.iaf_app.container.order_repository()
        self.iaf_app.run(number_of_iterations=1)
        response = self.client.get("api/portfolios")
        data = json.loads(response.data.decode())
        self.assertEqual(200, response.status_code)
        self.assertEqual(1, len(data["items"]))
