from investing_algorithm_framework import PortfolioConfiguration, Order, \
    MarketCredential
from investing_algorithm_framework.services import PortfolioService, \
    OrderService
from tests.resources import FlaskTestBase
from tests.resources import MarketServiceStub


class Test(FlaskTestBase):
    """
    Test for functionality of algorithm get_unfilled_buy_value
    """
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR",
            initial_balance=1000,
        )
    ]
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]

    def test_get_unfilled_buy_value(self):
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
                    "id": "14354",
                    "side": "buy",
                    "symbol": "DOT/EUR",
                    "amount": 10,
                    "price": 10.0,
                    "status": "OPEN",
                    "order_type": "limit",
                    "order_side": "buy",
                    "created_at": "2023-09-22T14:40:56.626362Z",
                    "filled": 0,
                    "remaining": 0,
                },
            ),
            Order.from_dict(
                {
                    "id": "49394",
                    "side": "buy",
                    "symbol": "ETH/EUR",
                    "amount": 10,
                    "price": 10.0,
                    "status": "OPEN",
                    "order_type": "limit",
                    "order_side": "buy",
                    "created_at": "2023-08-08T14:40:56.626362Z",
                    "filled": 0,
                    "remaining": 0,
                },
            ),
        ]
        market_service_stub.symbols = [
            "BTC/EUR", "DOT/EUR", "ADA/EUR", "ETH/EUR"
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
            2, order_service.count({"status": "OPEN"})
        )
        self.assertEqual(
            1, order_service.count({"target_symbol": "DOT"})
        )
        self.assertEqual(
            1, order_service.count({"target_symbol": "ETH"})
        )
        self.assertEqual(
            1, order_service.count({"target_symbol": "BTC"})
        )

        # Check that the portfolio has the correct amount of trades
        trade_service = self.iaf_app.container.trade_service()
        self.assertEqual(1, trade_service.count())
        self.assertEqual(
            1, trade_service.count(
                {"portfolio_id": portfolio.id, "status": "OPEN"}
            )
        )

        # Check if all positions are made
        position_service = self.iaf_app.container.position_service()
        self.assertEqual(4, position_service.count())

        # Check if btc position exists
        btc_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "BTC"}
        )
        self.assertEqual(10, btc_position.amount)

        # Check if dot position exists
        dot_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "DOT"}
        )
        self.assertEqual(0, dot_position.amount)

        # Check if eth position exists, but has amount set to 0
        eth_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "ETH"}
        )
        self.assertEqual(0, eth_position.amount)

        # Check if eur position exists
        eur_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "EUR"}
        )
        self.assertEqual(700, eur_position.amount)

        pending_orders = self.iaf_app.algorithm.get_pending_orders()
        self.assertEqual(2, len(pending_orders))

        # Check the unfilled buy value
        unfilled_buy_value = self.iaf_app.algorithm.get_unfilled_buy_value()
        self.assertEqual(200, unfilled_buy_value)

        pending_order = self.iaf_app.algorithm\
            .get_pending_orders(target_symbol="ETH")[0]

        order_service = self.iaf_app.container.order_service()
        order_service.update(
            pending_order.id,
            {
                "status": "CLOSED",
                "filled": pending_order.amount,
                "remaining": 0
            }
        )

        pending_orders = self.iaf_app.algorithm.get_pending_orders()
        self.assertEqual(1, len(pending_orders))

        # Check the unfilled buy value
        unfilled_buy_value = self.iaf_app.algorithm.get_unfilled_buy_value()
        self.assertEqual(100, unfilled_buy_value)
