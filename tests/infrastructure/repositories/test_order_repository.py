from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential
from tests.resources import TestBase


class Test(TestBase):
    market_credentials = [
        MarketCredential(
            market="BINANCE",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BINANCE",
            trading_symbol="EUR"
        )
    ]
    external_balances = {
        "EUR": 1000,
    }

    def test_get_all(self):
        self.app.run(number_of_iterations=1)
        order_service = self.app.container.order_service()
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.get_all()[0]
        order_service.create(
            {
                "portfolio_id": 1,
                "target_symbol": "BTC",
                "amount": 1,
                "trading_symbol": "EUR",
                "price": 10,
                "order_side": "BUY",
                "order_type": "LIMIT",
                "status": "OPEN",
            }
        )
        self.assertEqual(
            1, order_service.count({"portfolio_id": portfolio.id})
        )
        self.assertEqual(
            0, order_service.count(
                {"portfolio_id": f"{portfolio.id}aeokgopge"}
            )
        )
