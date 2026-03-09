"""
Consolidated tests for order-related context operations.

Merged from:
- test_create_limit_buy_order.py
- test_create_limit_sell_order.py
- test_check_order_status.py
- test_get_order.py
- test_has_open_buy_orders.py
- test_has_open_sell_orders.py
- test_get_pending_orders.py
- test_get_unfilled_buy_value.py
- test_get_unfilled_sell_value.py
"""
from decimal import Decimal
from unittest.mock import patch

from investing_algorithm_framework import PortfolioConfiguration, \
    OrderStatus, MarketCredential, Order
from investing_algorithm_framework.services import PortfolioService
from tests.resources import BitvavoTestBase, BinanceTestBase, TestBase
from tests.resources.strategies_for_testing import StrategyOne


# ---------------------------------------------------------------------------
# BITVAVO-based order tests
# ---------------------------------------------------------------------------

class TestCreateLimitBuyOrder(BitvavoTestBase):

    def count_decimals(self, number):
        decimal_str = str(number)
        if '.' in decimal_str:
            return len(decimal_str.split('.')[1])
        else:
            return 0

    def test_create_limit_buy_order(self):
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=10, order_side="BUY",
        )
        order_repository = self.app.container.order_repository()
        self.assertEqual(
            1,
            order_repository.count(
                {"order_type": "LIMIT", "order_side": "BUY"}
            )
        )
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.OPEN.value, order.status)

    @patch(
        "investing_algorithm_framework.services.data_providers"
        ".DataProviderService.get_ticker_data"
    )
    def test_create_limit_buy_order_with_percentage_of_portfolio(
        self, mock_get_ticker
    ):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR", "ask": 100, "bid": 90
        }
        self.app.add_strategy(StrategyOne)
        self.app.context.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="BUY",
            percentage_of_portfolio=20,
            precision=0
        )
        order_repository = self.app.container.order_repository()
        self.assertEqual(
            1, order_repository
            .count({"order_type": "LIMIT", "order_side": "BUY"})
        )
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.OPEN.value, order.status)
        self.assertEqual(20, order.get_amount())
        self.assertEqual(10, order.get_price())
        portfolio = self.app.context.get_portfolio()
        self.assertEqual(1000, portfolio.get_net_size())
        self.assertEqual(800, portfolio.get_unallocated())


class TestCreateLimitSellOrder(BitvavoTestBase):

    @patch(
        "investing_algorithm_framework.services.data_providers"
        ".DataProviderService.get_ticker_data"
    )
    def test_create_limit_sell_order(self, mock_get_ticker):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR", "bid": 10, "ask": 10, "last": 10
        }
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        self.app.context.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="BUY",
            percentage_of_portfolio=20,
            precision=0
        )
        order_repository = self.app.container.order_repository()
        self.assertEqual(
            1, order_repository
            .count({"order_type": "LIMIT", "order_side": "BUY"})
        )
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.OPEN.value, order.status)
        self.assertEqual(20, order.get_amount())
        self.assertEqual(10, order.get_price())
        portfolio = self.app.context.get_portfolio()
        self.assertEqual(1000, portfolio.get_net_size())
        self.assertEqual(800, portfolio.get_unallocated())
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.app.context.get_position("BTC")
        order = self.app.context.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="SELL",
            amount=20
        )
        self.assertEqual(20, order.get_amount())

    @patch(
        "investing_algorithm_framework.services.data_providers"
        ".DataProviderService.get_ticker_data"
    )
    def test_create_limit_sell_order_with_percentage_position(
        self, mock_get_ticker
    ):
        mock_get_ticker.return_value = {
            "symbol": "BTCEUR", "bid": 10, "ask": 10, "last": 10
        }
        self.app.add_strategy(StrategyOne)
        self.app.run(number_of_iterations=1)
        self.app.context.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="BUY",
            percentage_of_portfolio=20,
            precision=0
        )
        order_repository = self.app.container.order_repository()
        self.assertEqual(
            1, order_repository
            .count({"order_type": "LIMIT", "order_side": "BUY"})
        )
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.OPEN.value, order.status)
        self.assertEqual(20, order.get_amount())
        self.assertEqual(10, order.get_price())
        portfolio = self.app.context.get_portfolio()
        self.assertEqual(1000, portfolio.get_net_size())
        self.assertEqual(800, portfolio.get_unallocated())
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        order = self.app.context.create_limit_order(
            target_symbol="BTC",
            price=10,
            order_side="SELL",
            percentage_of_position=20
        )
        # 20% of 20 = 4
        self.assertEqual(4, order.get_amount())


class TestCheckOrderStatus(BitvavoTestBase):

    def test_check_order_status(self):
        order_repository = self.app.container.order_repository()
        position_repository = self.app.container.position_repository()
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=10, order_side="BUY",
        )
        self.assertEqual(1, order_repository.count())
        self.assertEqual(2, position_repository.count())
        self.app.context.order_service.check_pending_orders()
        self.assertEqual(1, order_repository.count())
        self.assertEqual(2, position_repository.count())
        order = order_repository.find({"target_symbol": "BTC"})
        self.assertEqual(OrderStatus.CLOSED.value, order.status)
        position = position_repository.find({"symbol": "BTC"})
        self.assertEqual(1, position.get_amount())


class TestGetOrder(BitvavoTestBase):

    def test_create_limit_buy_order_with_percentage_of_portfolio(self):
        order = self.app.context.create_limit_order(
            target_symbol="BTC", price=10, order_side="BUY", amount=20
        )
        self.assertEqual(OrderStatus.OPEN.value, order.status)
        self.assertEqual(Decimal(10), order.get_price())
        self.assertEqual(Decimal(20), order.get_amount())


# ---------------------------------------------------------------------------
# Binance-based order tests
# ---------------------------------------------------------------------------

class TestHasOpenBuyOrders(BinanceTestBase):

    def test_has_open_buy_orders(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(Decimal(1000), trading_symbol_position.get_amount())
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=10, order_side="BUY",
        )
        order_service = self.app.container.order_service()
        order_service.find({"symbol": "BTC/EUR"})
        self.app.container.position_service().find({"symbol": "BTC"})
        self.assertTrue(self.app.context.has_open_buy_orders("BTC"))
        order_service.check_pending_orders()
        self.assertFalse(self.app.context.has_open_buy_orders("BTC"))


class TestHasOpenSellOrders(BinanceTestBase):
    external_available_symbols = ["BTC/EUR", "DOT/EUR", "ADA/EUR", "ETH/EUR"]

    def test_has_open_sell_orders(self):
        trading_symbol_position = self.app.context.get_position("EUR")
        self.assertEqual(1000, trading_symbol_position.get_amount())
        self.assertFalse(self.app.context.position_exists(symbol="BTC"))
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=10, order_side="BUY",
        )
        order_service = self.app.container.order_service()
        order_service.check_pending_orders()
        self.app.context.create_limit_order(
            target_symbol="BTC", amount=1, price=10, order_side="SELL",
        )
        self.assertTrue(self.app.context.has_open_sell_orders("BTC"))
        order_service.check_pending_orders()
        self.assertFalse(self.app.context.has_open_sell_orders("BTC"))


# ---------------------------------------------------------------------------
# Tests with initial_orders (need custom class-level configuration)
# ---------------------------------------------------------------------------

class TestGetPendingOrders(TestBase):
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance", trading_symbol="EUR",
        )
    ]
    market_credentials = [
        MarketCredential(
            market="binance", api_key="api_key", secret_key="secret_key",
        )
    ]
    initial_orders = [
        Order.from_dict({
            "id": "1323", "side": "buy", "symbol": "BTC/EUR",
            "amount": 10, "price": 10.0, "status": "CLOSED",
            "order_type": "limit", "order_side": "buy",
            "created_at": "2023-08-08T14:40:56.626362Z",
            "filled": 10, "remaining": 0,
        }),
        Order.from_dict({
            "id": "14354", "side": "buy", "symbol": "DOT/EUR",
            "amount": 10, "price": 10.0, "status": "OPEN",
            "order_type": "limit", "order_side": "buy",
            "created_at": "2023-09-22T14:40:56.626362Z",
            "filled": 0, "remaining": 0,
        }),
        Order.from_dict({
            "id": "49394", "side": "buy", "symbol": "ETH/EUR",
            "amount": 10, "price": 10.0, "status": "OPEN",
            "order_type": "limit", "order_side": "buy",
            "created_at": "2023-08-08T14:40:56.626362Z",
            "filled": 0, "remaining": 0,
        }),
    ]

    def test_get_pending_orders(self):
        """
        Test that the portfolio service can sync existing orders
        from the market service to the order service.
        """
        portfolio_service: PortfolioService \
            = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})

        order_service = self.app.container.order_service()
        self.assertEqual(3, order_service.count())
        self.assertEqual(
            3, order_service.count({"portfolio": portfolio.id})
        )
        self.assertEqual(2, order_service.count({"status": "OPEN"}))
        self.assertEqual(
            1, order_service.count({"target_symbol": "DOT"})
        )
        self.assertEqual(
            1, order_service.count({"target_symbol": "ETH"})
        )
        self.assertEqual(
            1, order_service.count({"target_symbol": "BTC"})
        )

        trade_service = self.app.container.trade_service()
        self.assertEqual(3, trade_service.count())
        self.assertEqual(
            1, trade_service.count(
                {"portfolio_id": portfolio.id, "status": "OPEN"}
            )
        )

        position_service = self.app.container.position_service()
        self.assertEqual(4, position_service.count())

        btc_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "BTC"}
        )
        self.assertEqual(10, btc_position.amount)

        dot_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "DOT"}
        )
        self.assertEqual(0, dot_position.amount)

        eth_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "ETH"}
        )
        self.assertEqual(0, eth_position.amount)

        eur_position = position_service.find(
            {"portfolio_id": portfolio.id,
             "symbol": portfolio.trading_symbol}
        )
        self.assertEqual(700, eur_position.amount)

        pending_orders = self.app.context.get_pending_orders()
        self.assertEqual(2, len(pending_orders))

        pending_order = self.app.context \
            .get_pending_orders(target_symbol="ETH")[0]

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


class TestGetUnfilledBuyValue(TestBase):
    """
    Test for functionality of algorithm get_unfilled_buy_value
    """
    initial_orders = [
        Order.from_dict({
            "id": "1323", "side": "buy", "symbol": "BTC/EUR",
            "amount": 10, "price": 10.0, "status": "CLOSED",
            "order_type": "limit", "order_side": "buy",
            "created_at": "2023-08-08T14:40:56.626362Z",
            "filled": 10, "remaining": 0,
        }),
        Order.from_dict({
            "id": "14354", "side": "buy", "symbol": "DOT/EUR",
            "amount": 10, "price": 10.0, "status": "OPEN",
            "order_type": "limit", "order_side": "buy",
            "created_at": "2023-09-22T14:40:56.626362Z",
            "filled": 0, "remaining": 0,
        }),
        Order.from_dict({
            "id": "49394", "side": "buy", "symbol": "ETH/EUR",
            "amount": 10, "price": 10.0, "status": "OPEN",
            "order_type": "limit", "order_side": "buy",
            "created_at": "2023-08-08T14:40:56.626362Z",
            "filled": 0, "remaining": 0,
        })
    ]
    external_balances = {"EUR": 1000}
    portfolio_configurations = [
        PortfolioConfiguration(market="BITVAVO", trading_symbol="EUR")
    ]
    market_credentials = [
        MarketCredential(
            market="bitvavo", api_key="api_key", secret_key="secret_key"
        )
    ]

    def test_get_unfilled_buy_value(self):
        """
        Orders overview:
            - BTC/EUR: 10  10.0 (filled)
            - DOT/EUR: 10  10.0 (unfilled)
            - ETH/EUR: 10  10.0 (unfilled)

        The unfilled buy value should be 200
        The unallocated amount should be 700
        """
        portfolio_service: PortfolioService \
            = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "bitvavo"})

        order_service = self.app.container.order_service()
        self.assertEqual(3, order_service.count())
        self.assertEqual(
            3, order_service.count({"portfolio": portfolio.id})
        )
        self.assertEqual(2, order_service.count({"status": "OPEN"}))
        self.assertEqual(
            1, order_service.count({"target_symbol": "DOT"})
        )
        self.assertEqual(
            1, order_service.count({"target_symbol": "ETH"})
        )
        self.assertEqual(
            1, order_service.count({"target_symbol": "BTC"})
        )

        trade_service = self.app.container.trade_service()
        self.assertEqual(3, trade_service.count())
        self.assertEqual(
            1, trade_service.count(
                {"portfolio_id": portfolio.id, "status": "OPEN"}
            )
        )


class TestGetUnfilledSellValue(TestBase):
    """
    Test for functionality of algorithm get_unfilled_sell_value
    """
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance", trading_symbol="EUR", initial_balance=1000,
        )
    ]
    market_credentials = [
        MarketCredential(
            market="binance", api_key="api_key", secret_key="secret_key",
        )
    ]
    initial_orders = [
        Order.from_dict({
            "id": "1323", "side": "buy", "symbol": "BTC/EUR",
            "amount": 10, "price": 10.0, "status": "CLOSED",
            "order_type": "limit", "order_side": "buy",
            "created_at": "2023-08-08T14:40:56.626362Z",
            "filled": 10, "remaining": 0,
        }),
        Order.from_dict({
            "id": "132343", "order_side": "SELL", "symbol": "BTC/EUR",
            "amount": 10, "price": 20.0, "status": "CLOSED",
            "order_type": "limit",
            "created_at": "2023-08-08T14:40:56.626362Z",
            "filled": 10, "remaining": 0,
        }),
        Order.from_dict({
            "id": "14354", "side": "buy", "symbol": "DOT/EUR",
            "amount": 10, "price": 10.0, "status": "CLOSED",
            "order_type": "limit", "order_side": "buy",
            "created_at": "2023-09-22T14:40:56.626362Z",
            "filled": 10, "remaining": 0,
        }),
        Order.from_dict({
            "id": "49394", "side": "buy", "symbol": "ETH/EUR",
            "amount": 10, "price": 10.0, "status": "CLOSED",
            "order_type": "limit", "order_side": "buy",
            "created_at": "2023-08-08T14:40:56.626362Z",
            "filled": 10, "remaining": 0,
        }),
        Order.from_dict({
            "id": "4939424", "order_side": "sell", "symbol": "ETH/EUR",
            "amount": 10, "price": 10.0, "status": "OPEN",
            "order_type": "limit",
            "created_at": "2023-08-08T14:40:56.626362Z",
            "filled": 0, "remaining": 0,
        }),
        Order.from_dict({
            "id": "493943434", "order_side": "sell", "symbol": "DOT/EUR",
            "amount": 10, "price": 10.0, "status": "OPEN",
            "order_type": "limit",
            "created_at": "2023-08-08T14:40:56.626362Z",
            "filled": 0, "remaining": 0,
        }),
    ]
    external_balances = {"EUR": 1000}

    def test_get_unfilled_sell_value(self):
        """
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

        order_service = self.app.container.order_service()
        self.assertEqual(6, order_service.count())
        self.assertEqual(
            6, order_service.count({"portfolio": portfolio.id})
        )
        self.assertEqual(2, order_service.count({"status": "OPEN"}))
        self.assertEqual(
            2, order_service.count({"target_symbol": "DOT"})
        )
        self.assertEqual(
            2, order_service.count({"target_symbol": "ETH"})
        )
        self.assertEqual(
            2, order_service.count({"target_symbol": "BTC"})
        )

        trade_service = self.app.container.trade_service()
        self.assertEqual(3, trade_service.count())
        self.assertEqual(
            0, trade_service.count(
                {"portfolio_id": portfolio.id, "status": "OPEN"}
            )
        )

        position_service = self.app.container.position_service()
        self.assertEqual(4, position_service.count())

        btc_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "BTC"}
        )
        self.assertEqual(0, btc_position.amount)

        dot_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "DOT"}
        )
        self.assertEqual(0, dot_position.amount)

        eth_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "ETH"}
        )
        self.assertEqual(0, eth_position.amount)

        eur_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "EUR"}
        )
        self.assertEqual(900, eur_position.amount)

        pending_orders = self.app.context.get_pending_orders()
        self.assertEqual(2, len(pending_orders))

        unfilled_sell_value = self.app.context.get_unfilled_sell_value()
        self.assertEqual(200, unfilled_sell_value)

