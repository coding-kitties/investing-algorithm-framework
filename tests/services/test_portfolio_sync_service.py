from datetime import datetime
from tests.resources import TestBase

from investing_algorithm_framework import PortfolioConfiguration, Algorithm, \
    MarketCredential, OperationalException, RESERVED_BALANCES, APP_MODE, \
    Order, SYMBOLS


class Test(TestBase):
    initialize = False

    def test_sync_unallocated(self):
        """
        Test the sync_unallocated method of the PortfolioSyncService class.

        1. Create a PortfolioSyncService object.
        2. Create a portfolio with 1000 unallocated balance.
        3. Check if the portfolio still has the 1000 eu after the
        sync_unallocated method is called.
        """
        portfolio_sync_service = self.app.container.portfolio_sync_service()
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {"EUR": 1000}
        self.app.add_algorithm(Algorithm())
        self.app.initialize()

        portfolio = self.app.container.portfolio_service()\
            .find({"identifier": "test"})
        self.assertEqual(1000, portfolio.unallocated)

        # Sync again but with the new balance, if not stateless the
        # unallocated balance should be the same
        self.market_service.balances = {"EUR": 2000}
        portfolio_sync_service.sync_unallocated(portfolio)
        self.assertEqual(1000, portfolio.unallocated)

    def test_sync_unallocated_with_no_balance(self):
        """
        Test the sync_unallocated method of the PortfolioSyncService class.

        1. Create a PortfolioSyncService object.
        2. Create a portfolio with 1000 unallocated balance.
        3. Check if the portfolio still has the 1000 eu after the
        sync_unallocated method is called.
        """
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=1000
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {"EUR": 0}
        self.app.add_algorithm(Algorithm())

        with self.assertRaises(OperationalException):
            self.app.initialize()

    def test_sync_unallocated_with_reserved(self):
        configuration_service = self.app.container.configuration_service()
        configuration_service.config[RESERVED_BALANCES] = {"EUR": 500}
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=500
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {"EUR": 1200}
        self.app.add_algorithm(Algorithm())
        self.app.initialize()

        portfolio = self.app.container.portfolio_service() \
            .find({"identifier": "test"})
        self.assertEqual(500, portfolio.unallocated)

    def test_sync_unallocated_with_reserved_error(self):
        """
        Test the sync_unallocated method of the PortfolioSyncService class.

        1. Create a PortfolioSyncService object.
        2. Create a portfolio configuration with 500 unallocated balance.
        3. Set the reserved balance to 500.
        3. Set the market balance to 700
        4. Check if sync method raises an OperationalException.
        """
        configuration_service = self.app.container.configuration_service()
        configuration_service.config[RESERVED_BALANCES] = {"EUR": 500}
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=500
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {"EUR": 700}
        self.app.add_algorithm(Algorithm())

        with self.assertRaises(OperationalException):
            self.app.initialize()

    def test_sync_unallocated_with_initial_size(self):
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=500
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {"EUR": 1200}
        self.app.add_algorithm(Algorithm())
        self.app.initialize()

        portfolio = self.app.container.portfolio_service() \
            .find({"identifier": "test"})
        self.assertEqual(500, portfolio.unallocated)

    def test_sync_unallocated_with_stateless(self):
        """
        Test to sync the unallocated amount with initial load set to false.
        This means that if the available balance is less than the initial balance
        of the portfolio configuration, the unallocated balance should be set to the
        available balance. It should not raise an OperationalException.
        """
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=500
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {"EUR": 1200}
        self.app.add_algorithm(Algorithm())
        self.app._stateless = True
        self.app._web = False
        self.app.initialize()

        configuration_service = self.app.container.configuration_service()
        configuration_service.config[APP_MODE] = "STATELESS"
        portfolio = self.app.container.portfolio_service() \
            .find({"identifier": "test"})
        self.assertEqual(1200, portfolio.unallocated)

    def test_sync_positions(self):
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=500
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {
            "EUR": 1200,
            "BTC": 0.5,
            "ETH": 199,
            "ADA": 4023,
            "XRP": 10,
        }
        self.app.add_algorithm(Algorithm())
        self.app.initialize()
        configuration_service = self.app.container.configuration_service()
        configuration_service.config[APP_MODE] = "STATELESS"
        portfolio = self.app.container.portfolio_service() \
            .find({"identifier": "test"})
        self.assertEqual(500, portfolio.unallocated)
        btc_position = self.app.container.position_service().find(
            {"symbol": "BTC", "portfolio_id": portfolio.id}
        )
        self.assertEqual(0.5, btc_position.amount)
        eth_position = self.app.container.position_service().find(
            {"symbol": "ETH", "portfolio_id": portfolio.id}
        )
        self.assertEqual(199, eth_position.amount)
        ada_position = self.app.container.position_service().find(
            {"symbol": "ADA", "portfolio_id": portfolio.id}
        )
        self.assertEqual(4023, ada_position.amount)
        xrp_position = self.app.container.position_service().find(
            {"symbol": "XRP", "portfolio_id": portfolio.id}
        )
        self.assertEqual(10, xrp_position.amount)

    def test_sync_positions_with_reserved(self):
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=500
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {
            "EUR": 1200,
            "BTC": 0.5,
            "ETH": 199,
            "ADA": 4023,
            "XRP": 10,
        }
        self.app.add_algorithm(Algorithm())
        configuration_service = self.app.container.configuration_service()
        configuration_service.config[APP_MODE] = "STATELESS"
        configuration_service.config[RESERVED_BALANCES] = {
            "BTC": 0.5,
            "ETH": 1,
            "ADA": 1000,
            "XRP": 5
        }
        self.app.initialize()

        portfolio = self.app.container.portfolio_service() \
            .find({"identifier": "test"})
        self.assertEqual(500, portfolio.unallocated)
        self.assertFalse(
            self.app.container.position_service().exists({
                "symbol": "BTC",
                "portfolio_id": portfolio.id,
            })
        )
        eth_position = self.app.container.position_service().find(
            {"symbol": "ETH", "portfolio_id": portfolio.id}
        )
        self.assertEqual(198, eth_position.amount)
        ada_position = self.app.container.position_service().find(
            {"symbol": "ADA", "portfolio_id": portfolio.id}
        )
        self.assertEqual(3023, ada_position.amount)
        xrp_position = self.app.container.position_service().find(
            {"symbol": "XRP", "portfolio_id": portfolio.id}
        )
        self.assertEqual(5, xrp_position.amount)

        self.market_service.balances = {
            "BTC": 0.6,
            "ETH": 200,
            "ADA": 1000,
            "XRP": 5
        }
        portfolio_sync_service = self.app.container.portfolio_sync_service()
        portfolio_sync_service.sync_positions(portfolio)
        btc_position = self.app.container.position_service().find(
            {"symbol": "BTC", "portfolio_id": portfolio.id}
        )
        self.assertAlmostEqual(0.1, btc_position.amount)
        eth_position = self.app.container.position_service().find(
            {"symbol": "ETH", "portfolio_id": portfolio.id}
        )
        self.assertEqual(199, eth_position.amount)
        ada_position = self.app.container.position_service().find(
            {"symbol": "ADA", "portfolio_id": portfolio.id}
        )
        self.assertEqual(0, ada_position.amount)
        xrp_position = self.app.container.position_service().find(
            {"symbol": "XRP", "portfolio_id": portfolio.id}
        )
        self.assertEqual(0, xrp_position.amount)

    def test_sync_orders(self):
        """
        Test the sync_orders method of the PortfolioSyncService class.

        1. Create a PortfolioSyncService object.
        2. Create a portfolio with 1000 unallocated balance.
        3. 4 orders are synced to the portfolio.
        4. Check if the portfolio still has the 1000eu
        """
        configuration_service = self.app.container.configuration_service()
        configuration_service.config[SYMBOLS] = ["KSM"]
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=500
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {
            "EUR": 1200,
            "BTC": 0.5,
            "ETH": 199,
            "ADA": 4023,
            "XRP": 10,
        }
        self.market_service.orders = [
            Order.from_ccxt_order(
                {
                    "id": "12333535",
                    "symbol": "BTC/EUR",
                    "amount": 0.5,
                    "price": 50000,
                    "side": "buy",
                    "status": "open",
                    "type": "limit",
                    "datetime": "2021-10-10T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "1233353",
                    "symbol": "ETH/EUR",
                    "amount": 199,
                    "price": 2000,
                    "side": "buy",
                    "status": "open",
                    "type": "limit",
                    "datetime": "2021-10-10T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "1233",
                    "symbol": "ADA/EUR",
                    "amount": 4023,
                    "price": 1,
                    "side": "buy",
                    "status": "closed",
                    "type": "limit",
                    "datetime": "2021-10-10T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "123",
                    "symbol": "XRP/EUR",
                    "amount": 10,
                    "price": 1,
                    "side": "buy",
                    "type": "limit",
                    "status": "closed",
                    "datetime": "2021-10-10T10:10:10"
                }
            )
        ]

        self.app.add_algorithm(Algorithm())
        self.app.initialize()
        portfolio = self.app.container.portfolio_service() \
            .find({"identifier": "test"})
        order_service = self.app.container.order_service()
        position_service = self.app.container.position_service()
        btc_position = position_service.find(
            {"symbol": "BTC", "portfolio_id": portfolio.id}
        )
        self.assertEqual(1, order_service.count({"position": btc_position.id}))
        eth_position = self.app.container.position_service().find(
            {"symbol": "ETH", "portfolio_id": portfolio.id}
        )
        self.assertEqual(1, order_service.count({"position": eth_position.id}))
        orders = order_service.get_all(
            {"position": eth_position.id}
        )
        order = orders[0]
        self.assertEqual(199, order.amount)
        self.assertEqual(2000, order.price)
        self.assertEqual("BUY", order.order_side)
        self.assertEqual("LIMIT", order.order_type)
        self.assertEqual("OPEN", order.status)

        ada_position = self.app.container.position_service().find(
            {"symbol": "ADA", "portfolio_id": portfolio.id}
        )
        self.assertEqual(1, order_service.count({"position": ada_position.id}))
        orders = order_service.get_all(
            {"position": ada_position.id}
        )
        order = orders[0]
        self.assertEqual(4023, order.amount)
        self.assertEqual(1, order.price)
        self.assertEqual("BUY", order.order_side)
        self.assertEqual("LIMIT", order.order_type)
        self.assertEqual("CLOSED", order.status)

        xrp_position = self.app.container.position_service().find(
            {"symbol": "XRP", "portfolio_id": portfolio.id}
        )
        self.assertEqual(1, order_service.count({"position": xrp_position.id}))
        orders = order_service.get_all(
            {"position": xrp_position.id}
        )
        order = orders[0]
        self.assertEqual(10, order.amount)
        self.assertEqual(1, order.price)
        self.assertEqual("BUY", order.order_side)
        self.assertEqual("LIMIT", order.order_type)
        self.assertEqual("CLOSED", order.status)

        ksm_position = self.app.container.position_service().find(
            {"symbol": "KSM", "portfolio_id": portfolio.id}
        )
        self.assertIsNotNone(ksm_position)
        self.assertEqual(0, order_service.count({"position": ksm_position.id}))

    def test_sync_orders_with_track_from_attribute_set(self):
        """
        Test the sync_orders method of the PortfolioSyncService class with
        the track_from attribute set.

        1. Create a PortfolioSyncService object.
        2. Create a portfolio with 1000 unallocated balance.
        3. 4 orders are synced to the portfolio.
        4. Check if the portfolio still has the 1000eu
        """
        configuration_service = self.app.container.configuration_service()
        configuration_service.config[SYMBOLS] = ["KSM"]

        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=500,
                track_from="2021-10-10T10:10:10"
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {
            "EUR": 1200,
            "BTC": 0.5,
            "ETH": 199,
            "ADA": 4023,
            "XRP": 10,
        }
        self.market_service.orders = [
            Order.from_ccxt_order(
                {
                    "id": "12333535",
                    "symbol": "BTC/EUR",
                    "amount": 0.5,
                    "price": 50000,
                    "side": "buy",
                    "status": "open",
                    "type": "limit",
                    "datetime": "2021-09-10T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "1233353",
                    "symbol": "ETH/EUR",
                    "amount": 199,
                    "price": 2000,
                    "side": "buy",
                    "status": "open",
                    "type": "limit",
                    "datetime": "2021-09-10T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "1233",
                    "symbol": "ADA/EUR",
                    "amount": 4023,
                    "price": 1,
                    "side": "buy",
                    "status": "open",
                    "type": "limit",
                    "datetime": "2021-10-10T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "123",
                    "symbol": "XRP/EUR",
                    "amount": 10,
                    "price": 1,
                    "side": "buy",
                    "type": "limit",
                    "status": "open",
                    "datetime": "2021-10-10T10:10:10"
                }
            )
        ]

        self.app.add_algorithm(Algorithm())
        self.app.initialize()
        portfolio = self.app.container.portfolio_service() \
            .find({"identifier": "test"})
        self.assertEqual(500, portfolio.unallocated)
        btc_position = self.app.container.position_service().find(
            {"symbol": "BTC", "portfolio_id": portfolio.id}
        )
        order_service = self.app.container.order_service()
        self.assertEqual(0, order_service.count({"position": btc_position.id}))

        eth_position = self.app.container.position_service().find(
            {"symbol": "ETH", "portfolio_id": portfolio.id}
        )
        self.assertEqual(0, order_service.count({"position": eth_position.id}))

        ada_position = self.app.container.position_service().find(
            {"symbol": "ADA", "portfolio_id": portfolio.id}
        )
        self.assertEqual(1, order_service.count({"position": ada_position.id}))

        xrp_position = self.app.container.position_service().find(
            {"symbol": "XRP", "portfolio_id": portfolio.id}
        )
        self.assertEqual(1, order_service.count({"position": xrp_position.id}))

        ksm_position = self.app.container.position_service().find(
            {"symbol": "KSM", "portfolio_id": portfolio.id}
        )
        self.assertEqual(0, order_service.count({"position": ksm_position.id}))

    def test_sync_trades(self):
        configuration_service = self.app.container.configuration_service()
        configuration_service.config[SYMBOLS] = ["KSM/EUR"]

        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=500,
                track_from="2021-10-10T10:10:10"
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {
            "EUR": 1200,
            "BTC": 0.5,
            "ETH": 199,
            "ADA": 4023,
            "XRP": 10,
        }
        self.market_service.orders = [
            Order.from_ccxt_order(
                {
                    "id": "12333535",
                    "symbol": "BTC/EUR",
                    "amount": 0.5,
                    "filled": 0.3,
                    "remaining": 0.2,
                    "price": 50000,
                    "side": "buy",
                    "status": "open",
                    "type": "limit",
                    "datetime": "2021-09-10T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "1233353",
                    "symbol": "ETH/EUR",
                    "amount": 199,
                    "filled": 100,
                    "remaining": 99,
                    "price": 2000,
                    "side": "buy",
                    "status": "open",
                    "type": "limit",
                    "datetime": "2021-09-10T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "1233",
                    "symbol": "ADA/EUR",
                    "amount": 4023,
                    "filled": 4023,
                    "remaining": 0,
                    "price": 1,
                    "side": "buy",
                    "status": "closed",
                    "type": "limit",
                    "datetime": "2021-10-12T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "1233324",
                    "symbol": "ADA/EUR",
                    "amount": 4023,
                    "filled": 4023,
                    "remaining": 0,
                    "price": 1.10,
                    "side": "sell",
                    "status": "closed",
                    "type": "limit",
                    "datetime": "2021-10-13T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "123",
                    "symbol": "XRP/EUR",
                    "amount": 10,
                    "filled": 5,
                    "remaining": 5,
                    "price": 1,
                    "side": "buy",
                    "type": "limit",
                    "status": "open",
                    "datetime": "2021-10-10T10:10:10"
                }
            )
        ]

        self.app.add_algorithm(Algorithm())
        self.app.initialize()

        # Get ada buy order
        portfolio = self.app.container.portfolio_service() \
            .find({"identifier": "test"})
        order_service = self.app.container.order_service()
        ada_position = self.app.container.position_service().find(
            {"symbol": "ADA", "portfolio_id": portfolio.id}
        )
        orders = order_service.get_all(
            {"position": ada_position.id, "order_side": "buy"}
        )
        ada_buy_order = orders[0]
        self.assertEqual(4023, ada_buy_order.amount)
        self.assertEqual(1, ada_buy_order.price)
        self.assertEqual("BUY", ada_buy_order.order_side)
        self.assertEqual("LIMIT", ada_buy_order.order_type)
        self.assertEqual("CLOSED", ada_buy_order.status)
        self.assertEqual(
            datetime(
                year=2021, month=10, day=13, hour=10, minute=10, second=10
            ),
            ada_buy_order.get_trade_closed_at()
        )
        self.assertEqual(4023, ada_buy_order.get_filled())
        self.assertEqual(0, ada_buy_order.get_remaining())
        self.assertAlmostEqual(4023 * 0.1, ada_buy_order.get_net_gain())

    def test_sync_trades_stateless(self):
        configuration_service = self.app.container.configuration_service()
        configuration_service.config[SYMBOLS] = ["KSM/EUR"]
        configuration_service.config[APP_MODE] = "STATELESS"

        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=500,
                track_from="2021-10-10T10:10:10"
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test"
            )
        )
        self.market_service.balances = {
            "EUR": 1200,
            "BTC": 0.5,
            "ETH": 199,
            "ADA": 4023,
            "XRP": 10,
        }
        self.market_service.orders = [
            Order.from_ccxt_order(
                {
                    "id": "12333535",
                    "symbol": "BTC/EUR",
                    "amount": 0.5,
                    "filled": 0.3,
                    "remaining": 0.2,
                    "price": 50000,
                    "side": "buy",
                    "status": "open",
                    "type": "limit",
                    "datetime": "2021-09-10T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "1233353",
                    "symbol": "ETH/EUR",
                    "amount": 199,
                    "filled": 100,
                    "remaining": 99,
                    "price": 2000,
                    "side": "buy",
                    "status": "open",
                    "type": "limit",
                    "datetime": "2021-09-10T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "1233",
                    "symbol": "ADA/EUR",
                    "amount": 4023,
                    "filled": 4023,
                    "remaining": 0,
                    "price": 1,
                    "side": "buy",
                    "status": "closed",
                    "type": "limit",
                    "datetime": "2021-10-12T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "1233324",
                    "symbol": "ADA/EUR",
                    "amount": 4023,
                    "filled": 4023,
                    "remaining": 0,
                    "price": 1.10,
                    "side": "sell",
                    "status": "closed",
                    "type": "limit",
                    "datetime": "2021-10-13T10:10:10"
                },
            ),
            Order.from_ccxt_order(
                {
                    "id": "123",
                    "symbol": "XRP/EUR",
                    "amount": 10,
                    "filled": 5,
                    "remaining": 5,
                    "price": 1,
                    "side": "buy",
                    "type": "limit",
                    "status": "open",
                    "datetime": "2021-10-10T10:10:10"
                }
            )
        ]

        self.app.add_algorithm(Algorithm())
        self.app.initialize()

        # Get ada buy order
        portfolio = self.app.container.portfolio_service() \
            .find({"identifier": "test"})
        order_service = self.app.container.order_service()
        ada_position = self.app.container.position_service().find(
            {"symbol": "ADA", "portfolio_id": portfolio.id}
        )
        orders = order_service.get_all(
            {"position": ada_position.id, "order_side": "buy"}
        )
        ada_buy_order = orders[0]
        self.assertEqual(4023, ada_buy_order.amount)
        self.assertEqual(1, ada_buy_order.price)
        self.assertEqual("BUY", ada_buy_order.order_side)
        self.assertEqual("LIMIT", ada_buy_order.order_type)
        self.assertEqual("CLOSED", ada_buy_order.status)
        self.assertEqual(
            datetime(
                year=2021, month=10, day=13, hour=10, minute=10, second=10
            ),
            ada_buy_order.get_trade_closed_at()
        )
        self.assertEqual(4023, ada_buy_order.get_filled())
        self.assertEqual(0, ada_buy_order.get_remaining())
        self.assertAlmostEqual(4023 * 0.1, ada_buy_order.get_net_gain())
