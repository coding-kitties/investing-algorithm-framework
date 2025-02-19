from investing_algorithm_framework import Order, PortfolioConfiguration, \
    MarketCredential
from tests.resources import TestBase


class Test(TestBase):
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
                "id": "1323",
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
    external_orders = [
        Order.from_dict(
            {
                "id": "1323",
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
        # Order that is not tracked by the trading bot
        Order.from_dict(
            {
                "id": "133423",
                "side": "buy",
                "symbol": "KSM/EUR",
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
    ]
    external_balances = {"EUR": 1000}
    portfolio_configurations = [
        PortfolioConfiguration(
            market="BITVAVO",
            trading_symbol="EUR"
        )
    ]
    market_credentials = [
        MarketCredential(
            market="bitvavo",
            api_key="api_key",
            secret_key="secret_key"
        )
    ]

    def test_start_with_new_external_positions(self):
        """
        Test how the framework handles new external positions on an broker or
        exchange.

        If the positions where not in the database, the algorithm should
        not include them, because they could be positions from another
        user or from another algorithm.
        """
        self.assertTrue(self.app.context.has_position("BTC"))
        btc_position = self.app.context.get_position("BTC")
        self.assertEqual(10, btc_position.get_amount())
        self.assertTrue(self.app.context.has_position("DOT"))
        dot_position = self.app.context.get_position("DOT")
        self.assertEqual(10, dot_position.get_amount())
        # Eth position still has open order
        self.assertFalse(self.app.context.has_position("ETH"))
        eth_position = self.app.context.get_position("ETH")
        self.assertEqual(0, eth_position.get_amount())
        self.assertFalse(self.app.context.has_position("KSM"))
        self.app.run(number_of_iterations=1)
        self.assertTrue(self.app.context.has_position("BTC"))
        btc_position = self.app.context.get_position("BTC")
        self.assertEqual(10, btc_position.get_amount())
        self.assertTrue(self.app.context.has_position("DOT"))
        dot_position = self.app.context.get_position("DOT")
        self.assertEqual(10, dot_position.get_amount())
        self.assertTrue(self.app.context.has_position("ETH"))
        eth_position = self.app.context.get_position("ETH")
        self.assertEqual(10, eth_position.get_amount())
        self.assertFalse(self.app.context.has_position("KSM"))
