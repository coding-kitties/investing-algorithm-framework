from tests.resources import FlaskTestBase
from tests.resources import MarketServiceStub

from investing_algorithm_framework.services import PortfolioService, \
    MarketCredentialService
from investing_algorithm_framework import PortfolioConfiguration, Order


class TestPortfolioService(FlaskTestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
            initial_balance=1000,
        )
    ]

    def test_sync_portfolio_orders(self):
        """
        Test that the portfolio service can sync existing orders

        The test should make sure that the portfolio service can sync
        existing orders from the market service to the order service.
        """
        portfolio_service: PortfolioService \
            = self.iaf_app.container.portfolio_service()
        market_service_stub = MarketServiceStub(None)
        market_service_stub.orders = [
            Order.from_dict(
                {
                    "id": "1323",
                    "side": "buy",
                    "symbol": "BTC/EUR",
                    "amount": 10,
                    "price": 10.0,
                    "status": "CLOSED",
                    "order_type": "limit",
                    "order_side": "buy",
                    "created_at": "2023-08-08T14:40:56.626362Z",
                    "filled": 10,
                    "remaining": 0,
                },
            ),
            Order.from_dict(
                {
                    "id": "2332",
                    "side": "sell",
                    "symbol": "BTC/EUR",
                    "amount": 10,
                    "price": 20.0,
                    "status": "CLOSED",
                    "order_type": "limit",
                    "order_side": "sell",
                    "created_at": "2023-08-10T14:40:56.626362Z",
                    "filled": 10,
                    "remaining": 0,
                },
            ),
            Order.from_dict(
                {
                    "id": "14354",
                    "side": "buy",
                    "symbol": "DOT/EUR",
                    "amount": 10,
                    "price": 10.0,
                    "status": "CLOSED",
                    "order_type": "limit",
                    "order_side": "buy",
                    "created_at": "2023-09-22T14:40:56.626362Z",
                    "filled": 10,
                    "remaining": 0,
                },
            ),
        ]
        portfolio_service.market_service = market_service_stub
        portfolio = portfolio_service.find({"market": "binance"})
        portfolio_service.sync_portfolio_orders(portfolio)

        # Check that the portfolio has the correct amount of orders
        order_service = self.iaf_app.container.order_service()
        self.assertEqual(3, order_service.count())
        self.assertEqual(
            3, order_service.count({"portfolio": portfolio.id})
        )
        self.assertEqual(
            2, order_service.count({"target_symbol": "BTC"})
        )
        self.assertEqual(
            0, order_service.count({"portfolio_id": 2321})
        )
        self.assertEqual(
            1, order_service.count({"target_symbol": "DOT"})
        )

        trade_service = self.iaf_app.container.trade_service()
        self.assertEqual(2, trade_service.count())
        self.assertEqual(
            1, trade_service.count(
                {"portfolio_id": portfolio.id, "status": "CLOSED"}
            )
        )
        self.assertEqual(
            1, trade_service.count(
                {"portfolio_id": portfolio.id, "status": "OPEN"}
            )
        )
