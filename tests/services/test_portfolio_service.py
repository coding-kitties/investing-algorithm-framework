from investing_algorithm_framework import PortfolioConfiguration, Order, \
    MarketCredential, RESERVED_BALANCES
from investing_algorithm_framework.services import PortfolioService, \
    OrderService
from tests.resources import FlaskTestBase
from tests.resources import MarketServiceStub


class TestPortfolioService(FlaskTestBase):
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

    def test_sync_portfolio_balances(self):
        portfolio_configuration_service = self.iaf_app.container \
            .portfolio_configuration_service()
        portfolio_configuration_service.clear()
        portfolio_configuration_service.add(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="EUR",
            )
        )
        portfolio_service: PortfolioService \
            = self.iaf_app.container.portfolio_service()

        market_service_stub = MarketServiceStub(None)
        market_service_stub.balances = {
            "EUR": 1000,
            "BTC": 20,
        }
        portfolio_service.market_service = market_service_stub
        portfolio = portfolio_service.find({"market": "binance"})
        portfolio_service.sync_portfolio_balances(portfolio)
        self.assertEqual(1000, portfolio.unallocated)
        position_service = self.iaf_app.container.position_service()
        self.assertEqual(2, position_service.count())
        self.assertEqual(1000, position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "EUR"}
        ).amount)
        self.assertEqual(20, position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "BTC"}
        ).amount)

        # Test when a new sync is ma de the unallocated amount is updated
        market_service_stub.balances = {
            "EUR": 2000,
            "BTC": 30,
        }

        portfolio_service.sync_portfolio_balances(portfolio)
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(2000, position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "EUR"}
        ).amount)
        self.assertEqual(30, position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "BTC"}
        ).amount)

    def test_create_portfolio_configuration(self):
        portfolio_service: PortfolioService \
            = self.iaf_app.container.portfolio_service()

        market_service_stub = MarketServiceStub(None)
        market_service_stub.balances = {
            "EUR": 1000,
            "BTC": 20,
        }
        portfolio_service.market_service = market_service_stub
        portfolio = portfolio_service.find({"market": "binance"})
        portfolio_service.create_portfolio_from_configuration(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="EUR",
            )
        )
        self.assertEqual(1000, portfolio.unallocated)

        # Test when a new sync is ma de the unallocated is not updated
        # Because it already exists
        market_service_stub.balances = {
            "EUR": 2000,
            "BTC": 30,
        }
        portfolio_service.create_portfolio_from_configuration(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="EUR",
            )
        )
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(1000, portfolio.unallocated)

    def test_sync_create_portfolio_configuration_with_reserved(self):
        self.iaf_app.config[RESERVED_BALANCES] = {
            "EUR": 100,
            "BTC": 10,
        }
        configuration_service = self.iaf_app.container.configuration_service()
        configuration_service.config[RESERVED_BALANCES] = {
            "EUR": 100,
            "BTC": 10,
        }
        portfolio_configuration_service = self.iaf_app.container \
            .portfolio_configuration_service()
        portfolio_configuration_service.clear()
        portfolio_configuration_service.add(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="EUR",
            )
        )
        portfolio_service: PortfolioService \
            = self.iaf_app.container.portfolio_service()

        market_service_stub = MarketServiceStub(None)
        market_service_stub.balances = {
            "EUR": 1000,
            "BTC": 20,
        }
        portfolio_service.market_service = market_service_stub
        portfolio = portfolio_service.find({"market": "binance"})
        portfolio_service.create_portfolio_from_configuration(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        self.assertEqual(900, portfolio.unallocated)

    def test_sync_portfolio_balances_with_reserved_balances(self):
        self.iaf_app.config[RESERVED_BALANCES] = {
            "EUR": 100,
            "BTC": 10,
        }
        portfolio_configuration_service = self.iaf_app.container \
            .portfolio_configuration_service()
        portfolio_configuration_service.clear()
        portfolio_configuration_service.add(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="EUR",
            )
        )
        portfolio_service: PortfolioService \
            = self.iaf_app.container.portfolio_service()

        market_service_stub = MarketServiceStub(None)
        market_service_stub.balances = {
            "EUR": 1000,
            "BTC": 20,
        }
        portfolio_service.market_service = market_service_stub
        portfolio = portfolio_service.find({"market": "binance"})
        portfolio_service.sync_portfolio_balances(portfolio)

        position_service = self.iaf_app.container.position_service()
        self.assertEqual(2, position_service.count())
        self.assertEqual(900, position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "EUR"}
        ).amount)
        self.assertEqual(10, position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "BTC"}
        ).amount)

        # Test when a new sync is ma de the unallocated amount is updated
        market_service_stub.balances = {
            "EUR": 2000,
            "BTC": 30,
        }

        portfolio_service.sync_portfolio_balances(portfolio)
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(1900, position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "EUR"}
        ).amount)
        self.assertEqual(20, position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "BTC"}
        ).amount)

    def test_sync_portfolio_orders(self):
        """
        In stateless mode, the portfolio service should first retrieve
        the unallocated amount. Then it should load in all its orders and
        positions. The orders should not update its unallocated amount, but
        they should update the positions.
        """
        portfolio_configuration_service = self.iaf_app.container \
            .portfolio_configuration_service()
        portfolio_configuration_service.clear()

        # This should not be necessary, but it is here to make sure that
        # the portfolio configuration is not being loaded from the database
        # when it should not be. In stateless mode the trading bot
        # can't keep track of the unallocated amount. Therefore, it reads
        # the full amount from the exchange.
        portfolio_configuration_service.add(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="EUR",
                initial_balance=500,
            )
        )
        portfolio_service: PortfolioService \
            = self.iaf_app.container.portfolio_service()
        market_service_stub = MarketServiceStub(None)
        market_service_stub.balances = {"EUR": 1000}
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
            Order.from_dict(
                {
                    "id": "14354435",
                    "side": "sell",
                    "symbol": "DOT/EUR",
                    "amount": 10,
                    "price": 11.0,
                    "status": "CLOSED",
                    "order_type": "limit",
                    "order_side": "buy",
                    "created_at": "2023-09-23T14:40:56.626362Z",
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
        self.assertEqual(500, portfolio.unallocated)





    def test_sync_portfolio_orders_without_position_and_unallocated_sync(self):
        """
        Test that the portfolio service can sync existing orders

        The test should make sure that the portfolio service can sync
        existing orders from the market service to the order service.
        """
        portfolio_configuration_service = self.iaf_app.container\
            .portfolio_configuration_service()
        portfolio_configuration_service.clear()
        portfolio_configuration_service.add(
            PortfolioConfiguration(
                market="binance",
                trading_symbol="EUR",
                initial_balance=1000,
            )
        )
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
        self.assertEqual(4, order_service.count())
        self.assertEqual(
            4, order_service.count({"portfolio": portfolio.id})
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
        self.assertEqual(
            1, order_service.count({"target_symbol": "ETH"})
        )

        # Check that the portfolio has the correct amount of trades
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

        # Check if all positions are made
        position_service = self.iaf_app.container.position_service()
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
        self.assertEqual(10, dot_position.amount)

        # Check if eth position exists, but has amount set to 0
        eth_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "ETH"}
        )
        self.assertEqual(0, eth_position.amount)

        # Check if eur position exists
        eur_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "EUR"}
        )
        self.assertEqual(1000, eur_position.amount)

        # Check that there is the correct amount of pending orders
        order_service: OrderService = self.iaf_app.container.order_service()
        self.assertEqual(1, order_service.count({"status": "OPEN"}))
        pending_orders = self.iaf_app.algorithm.get_pending_orders()
        self.assertEqual(1, len(pending_orders))
        self.assertEqual(10, pending_orders[0].amount)

    def test_sync_portfolio_orders_with_symbols_config(self):
        """
        Test that the portfolio service can sync existing orders with
        symbols configuration in the app config.

        The test should make sure that the portfolio service can sync
        existing orders from the market service to the order service. It
        should also only sync orders that are in the symbols configuration
        in the app config.
        """
        configuration_service = self.iaf_app.container.configuration_service()
        configuration_service.config["SYMBOLS"] = ["BTC/EUR", "DOT/EUR"]
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
            2, order_service.count({"target_symbol": "BTC"})
        )
        self.assertEqual(
            0, order_service.count({"portfolio_id": 2321})
        )
        self.assertEqual(
            1, order_service.count({"target_symbol": "DOT"})
        )
        self.assertEqual(
            0, order_service.count({"target_symbol": "ETH"})
        )

        # Check that the portfolio has the correct amount of trades
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

        # Check if all positions are made
        position_service = self.iaf_app.container.position_service()
        self.assertEqual(3, position_service.count())

        # Check if btc position exists
        btc_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "BTC"}
        )
        self.assertEqual(0, btc_position.amount)

        # Check if dot position exists
        dot_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "DOT"}
        )
        self.assertEqual(10, dot_position.amount)

        # Check if eur position exists
        eur_position = position_service.find(
            {"portfolio_id": portfolio.id, "symbol": "EUR"}
        )
        self.assertEqual(1000, eur_position.amount)

        # Check that there is the correct amount of pending orders
        order_service: OrderService = self.iaf_app.container.order_service()
        self.assertEqual(0, order_service.count({"status": "OPEN"}))
        pending_orders = self.iaf_app.algorithm.get_pending_orders()
        self.assertEqual(0, len(pending_orders))

