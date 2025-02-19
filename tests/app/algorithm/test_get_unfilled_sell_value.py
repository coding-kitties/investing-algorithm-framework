from investing_algorithm_framework import PortfolioConfiguration, Order, \
    MarketCredential
from investing_algorithm_framework.services import PortfolioService
from tests.resources import TestBase, MarketDataSourceServiceStub


class Test(TestBase):
    """
    Test for functionality of algorithm get_unfilled_sell_value
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
    initial_orders = [
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
                "id": "132343",
                "order_side": "SELL",
                "symbol": "BTC/EUR",
                "amount": 10,
                "price": 20.0,
                "status": "CLOSED",
                "order_type": "limit",
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
                "status": "CLOSED",
                "order_type": "limit",
                "order_side": "buy",
                "created_at": "2023-09-22T14:40:56.626362Z",
                "filled": 10,
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
                "id": "4939424",
                "order_side": "sell",
                "symbol": "ETH/EUR",
                "amount": 10,
                "price": 10.0,
                "status": "OPEN",
                "order_type": "limit",
                "created_at": "2023-08-08T14:40:56.626362Z",
                "filled": 0,
                "remaining": 0,
            },
        ),
        Order.from_dict(
            {
                "id": "493943434",
                "order_side": "sell",
                "symbol": "DOT/EUR",
                "amount": 10,
                "price": 10.0,
                "status": "OPEN",
                "order_type": "limit",
                "created_at": "2023-08-08T14:40:56.626362Z",
                "filled": 0,
                "remaining": 0,
            },
        ),
    ]
    external_balances = {
        "EUR": 1000
    }
    market_data_source_service = MarketDataSourceServiceStub()

    def test_get_unfilled_sell_value(self):
        """
        Test that the portfolio service can sync existing orders

        The test should make sure that the portfolio service can sync
        existing orders from the market service to the order service.

        Order overview:
            - BTC/EUR BUY 10 10.0
            - BTC/EUR SELL 10 20.0 (filled, profit 10*10=100)
            - DOT/EUR BUY 10 10.0
            - ETH/EUR BUY 10 10.0
            - ETH/EUR SELL 10 10.0 (unfilled)
            - DOT/EUR SELL 10 10.0 (unfilled)

        At the end of the order history unallocated amount should be 900
        """
        portfolio_service: PortfolioService \
            = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})

        # Check that the portfolio has the correct amount of orders
        order_service = self.app.container.order_service()
        self.assertEqual(6, order_service.count())
        self.assertEqual(
            6, order_service.count({"portfolio": portfolio.id})
        )
        self.assertEqual(
            2, order_service.count({"status": "OPEN"})
        )
        self.assertEqual(
            2, order_service.count({"target_symbol": "DOT"})
        )
        self.assertEqual(
            2, order_service.count({"target_symbol": "ETH"})
        )
        self.assertEqual(
            2, order_service.count({"target_symbol": "BTC"})
        )

        # Check that the portfolio has the correct amount of trades
        trade_service = self.app.container.trade_service()
        self.assertEqual(3, trade_service.count())
        self.assertEqual(
            0, trade_service.count(
                {"portfolio_id": portfolio.id, "status": "OPEN"}
            )
        )

        # Check if all positions are made
        position_service = self.app.container.position_service()
        self.assertEqual(4, position_service.count())

        # Check if btc position exists
        btc_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "BTC"}
        )
        self.assertEqual(0, btc_position.amount)

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
        self.assertEqual(900, eur_position.amount)

        pending_orders = self.app.context.get_pending_orders()
        self.assertEqual(2, len(pending_orders))

        # Check the unfilled sell value
        unfilled_sell_value = self.app.context.get_unfilled_sell_value()
        self.assertEqual(200, unfilled_sell_value)

        pending_order = self.app.context\
            .get_pending_orders(target_symbol="ETH")[0]

        order_service = self.app.container.order_service()
        order_service.update(
            pending_order.id,
            {
                "status": "CLOSED",
                "filled": pending_order.amount,
                "remaining": 0
            }
        )

        pending_orders = self.app.context.get_pending_orders()
        self.assertEqual(1, len(pending_orders))

        # Check the unfilled buy value
        unfilled_sell_value = self.app.context.get_unfilled_sell_value()
        self.assertEqual(100, unfilled_sell_value)

         # Check if eur position exists
        eur_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "EUR"}
        )
        self.assertEqual(1000, eur_position.amount)
