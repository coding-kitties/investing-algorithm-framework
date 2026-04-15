from investing_algorithm_framework import PortfolioConfiguration, \
    MarketCredential, OrderStatus, Algorithm, OperationalException
from tests.resources import TestBase


# ------------------------------------------------------------------ #
# Startup sync tests                                                   #
# ------------------------------------------------------------------ #


class TestStartupSyncUnallocated(TestBase):
    """Test sync_unallocated during initialize_portfolios on startup."""
    initialize = False

    def _init_app(self, initial_balance=None, external_eur=1000):
        portfolio_provider_lookup = \
            self.app.container.portfolio_provider_lookup()
        portfolio_provider_lookup.register_portfolio_provider_for_market(
            "binance"
        )
        portfolio_provider = \
            portfolio_provider_lookup.get_portfolio_provider("binance")
        portfolio_provider.external_balances = {"EUR": external_eur}

        config = {}
        if initial_balance is not None:
            config["initial_balance"] = initial_balance

        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=initial_balance,
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test",
            )
        )
        self.app.initialize_config()
        self.app.initialize_storage()
        self.app.initialize_services()

    def test_startup_sync_sets_unallocated_to_initial_balance(self):
        """With initial_balance=500 and 1000 EUR on exchange,
        unallocated should be set to 500."""
        self._init_app(initial_balance=500, external_eur=1000)
        self.app.initialize_portfolios()

        portfolio = self.app.container.portfolio_service().find(
            {"identifier": "test"}
        )
        self.assertEqual(500, portfolio.unallocated)
        self.assertTrue(portfolio.initialized)

    def test_startup_sync_uses_exchange_balance_when_no_initial(self):
        """Without initial_balance, unallocated should equal
        the full exchange balance."""
        self._init_app(initial_balance=None, external_eur=750)
        self.app.initialize_portfolios()

        portfolio = self.app.container.portfolio_service().find(
            {"identifier": "test"}
        )
        self.assertEqual(750, portfolio.unallocated)
        self.assertTrue(portfolio.initialized)

    def test_startup_sync_raises_when_initial_exceeds_exchange(self):
        """If initial_balance > exchange balance, startup should fail."""
        self._init_app(initial_balance=2000, external_eur=1000)
        with self.assertRaises(OperationalException):
            self.app.initialize_portfolios()

    def test_startup_sync_sets_trading_symbol_position(self):
        """The trading symbol position (EUR) should be set to the
        unallocated amount on first startup."""
        self._init_app(initial_balance=800, external_eur=1000)
        self.app.initialize_portfolios()

        portfolio = self.app.container.portfolio_service().find(
            {"identifier": "test"}
        )
        position_service = self.app.container.position_service()
        eur_position = position_service.find(
            {"symbol": "EUR", "portfolio": portfolio.id}
        )
        self.assertEqual(800, eur_position.get_amount())

    def test_startup_sync_sets_net_size(self):
        """net_size should be set to the unallocated value on first init."""
        self._init_app(initial_balance=600, external_eur=1000)
        self.app.initialize_portfolios()

        portfolio = self.app.container.portfolio_service().find(
            {"identifier": "test"}
        )
        self.assertEqual(600, portfolio.net_size)


class TestStartupSyncExistingPortfolio(TestBase):
    """Test sync_unallocated on restart with an already-initialized
    portfolio. The service should validate that the exchange has
    enough balance to cover the locally tracked unallocated amount."""
    initialize = False

    def _init_and_restart(self, initial_balance, external_eur_restart):
        """First init with `initial_balance`, then simulate restart
        with a different exchange balance."""
        self.app.add_portfolio_configuration(
            PortfolioConfiguration(
                identifier="test",
                market="binance",
                trading_symbol="EUR",
                initial_balance=initial_balance,
            )
        )
        self.app.add_market_credential(
            MarketCredential(
                market="binance",
                api_key="test",
                secret_key="test",
            )
        )
        self.app.initialize_config()
        self.app.initialize_storage()
        self.app.initialize_services()
        self.app.initialize_portfolios()  # first startup

        # Simulate restart: change what the exchange reports
        portfolio_provider_lookup = \
            self.app.container.portfolio_provider_lookup()
        portfolio_provider_lookup.register_portfolio_provider_for_market(
            "binance"
        )
        portfolio_provider = \
            portfolio_provider_lookup.get_portfolio_provider("binance")
        portfolio_provider.external_balances = {
            "EUR": external_eur_restart
        }

    def test_restart_succeeds_when_exchange_has_enough(self):
        """If the exchange still has >= unallocated, no error."""
        self._init_and_restart(
            initial_balance=500, external_eur_restart=600
        )
        portfolio_sync_service = \
            self.app.container.portfolio_sync_service()
        portfolio = self.app.container.portfolio_service().find(
            {"identifier": "test"}
        )
        # Should not raise
        portfolio_sync_service.sync_unallocated(portfolio)

    def test_restart_raises_when_exchange_balance_too_low(self):
        """If the exchange balance dropped below unallocated, raise."""
        self._init_and_restart(
            initial_balance=500, external_eur_restart=100
        )
        portfolio_sync_service = \
            self.app.container.portfolio_sync_service()
        portfolio = self.app.container.portfolio_service().find(
            {"identifier": "test"}
        )
        with self.assertRaises(OperationalException):
            portfolio_sync_service.sync_unallocated(portfolio)


class TestStartupSyncOrders(TestBase):
    """Test that sync_orders on startup reconciles pending orders
    with the exchange."""
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {"EUR": 1000}

    def test_startup_sync_fills_pending_buy_order(self):
        """An OPEN buy order should be filled when exchange says CLOSED."""
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 100,
                "order_side": "BUY",
                "price": 1.0,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )
        self.assertEqual(OrderStatus.OPEN.value, order.get_status())

        # Configure portfolio provider to report the order as CLOSED
        portfolio_provider_lookup = \
            self.app.container.portfolio_provider_lookup()
        portfolio_provider_lookup.register_portfolio_provider_for_market(
            "binance"
        )
        portfolio_provider = \
            portfolio_provider_lookup.get_portfolio_provider("binance")
        portfolio_provider.order_amount_filled = 100

        # Simulate startup sync
        portfolio_sync_service = \
            self.app.container.portfolio_sync_service()
        portfolio = self.app.container.portfolio_service().find(
            {"market": "binance"}
        )
        portfolio_sync_service.sync_orders(portfolio)

        order = order_service.get(order.id)
        self.assertEqual(OrderStatus.CLOSED.value, order.get_status())
        self.assertEqual(100, order.get_filled())

        # Position should now hold the filled amount
        position_service = self.app.container.position_service()
        position = position_service.get(order.position_id)
        self.assertEqual(100, position.get_amount())

    def test_startup_sync_cancels_pending_buy_order(self):
        """An OPEN buy order cancelled on exchange should restore balance."""
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 100,
                "order_side": "BUY",
                "price": 1.0,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(900, portfolio.get_unallocated())

        # Exchange says cancelled with nothing filled
        portfolio_provider_lookup = \
            self.app.container.portfolio_provider_lookup()
        portfolio_provider_lookup.register_portfolio_provider_for_market(
            "binance"
        )
        portfolio_provider = \
            portfolio_provider_lookup.get_portfolio_provider("binance")
        portfolio_provider.status = OrderStatus.CANCELED.value
        portfolio_provider.order_amount_filled = 0

        portfolio_sync_service = \
            self.app.container.portfolio_sync_service()
        portfolio_sync_service.sync_orders(portfolio)

        order = order_service.get(order.id)
        self.assertEqual(OrderStatus.CANCELED.value, order.get_status())

        # Balance should be fully restored
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(1000, portfolio.get_unallocated())

    def test_startup_sync_fills_pending_sell_order(self):
        """An OPEN sell order should be filled when exchange says CLOSED."""
        order_executor_lookup = self.app.container.order_executor_lookup()
        order_executor_lookup.register_order_executor_for_market("binance")
        order_executor = order_executor_lookup.get_order_executor("binance")
        order_executor.order_amount_filled = 500
        order_executor.order_status = OrderStatus.CLOSED.value

        order_service = self.app.container.order_service()
        # First create a filled buy to have a position
        buy_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 500,
                "order_side": "BUY",
                "price": 1.0,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )
        self.assertEqual(OrderStatus.CLOSED.value, buy_order.get_status())

        # Now create a sell order that stays open
        order_executor.order_amount_filled = 0
        order_executor.order_status = OrderStatus.OPEN.value
        sell_order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 500,
                "order_side": "SELL",
                "price": 2.0,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )
        self.assertEqual(OrderStatus.OPEN.value, sell_order.get_status())

        # Exchange reports the sell as filled
        portfolio_provider_lookup = \
            self.app.container.portfolio_provider_lookup()
        portfolio_provider_lookup.register_portfolio_provider_for_market(
            "binance"
        )
        portfolio_provider = \
            portfolio_provider_lookup.get_portfolio_provider("binance")
        portfolio_provider.order_amount_filled = 500

        portfolio_sync_service = \
            self.app.container.portfolio_sync_service()
        portfolio = self.app.container.portfolio_service().find(
            {"market": "binance"}
        )
        portfolio_sync_service.sync_orders(portfolio)

        sell_order = order_service.get(sell_order.id)
        self.assertEqual(OrderStatus.CLOSED.value, sell_order.get_status())
        self.assertEqual(500, sell_order.get_filled())

        # Should have received sell proceeds
        portfolio = self.app.container.portfolio_service().find(
            {"market": "binance"}
        )
        # 1000 - 500 (buy) + 1000 (sell at 2x) = 1500
        self.assertEqual(1500, portfolio.get_unallocated())

    def test_startup_sync_partial_fill_pending_order(self):
        """An OPEN buy order partially filled on exchange should update
        position and remaining."""
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 100,
                "order_side": "BUY",
                "price": 1.0,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        # Exchange reports 40 out of 100 filled, still open
        portfolio_provider_lookup = \
            self.app.container.portfolio_provider_lookup()
        portfolio_provider_lookup.register_portfolio_provider_for_market(
            "binance"
        )
        portfolio_provider = \
            portfolio_provider_lookup.get_portfolio_provider("binance")
        portfolio_provider.status = OrderStatus.OPEN.value
        portfolio_provider.order_amount_filled = 40

        portfolio_sync_service = \
            self.app.container.portfolio_sync_service()
        portfolio = self.app.container.portfolio_service().find(
            {"market": "binance"}
        )
        portfolio_sync_service.sync_orders(portfolio)

        order = order_service.get(order.id)
        self.assertEqual(OrderStatus.OPEN.value, order.get_status())
        self.assertEqual(40, order.get_filled())

        # Position should reflect the partial fill
        position_service = self.app.container.position_service()
        position = position_service.get(order.position_id)
        self.assertEqual(40, position.get_amount())

    def test_startup_sync_no_pending_orders_is_noop(self):
        """When there are no pending orders, sync_orders should be a noop."""
        portfolio_sync_service = \
            self.app.container.portfolio_sync_service()
        portfolio = self.app.container.portfolio_service().find(
            {"market": "binance"}
        )
        # Should not raise
        portfolio_sync_service.sync_orders(portfolio)

        # Portfolio unchanged
        portfolio = self.app.container.portfolio_service().find(
            {"market": "binance"}
        )
        self.assertEqual(1000, portfolio.get_unallocated())

    def test_startup_sync_multiple_pending_orders(self):
        """Multiple OPEN orders should all be synced on startup."""
        order_service = self.app.container.order_service()
        order1 = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 100,
                "order_side": "BUY",
                "price": 1.0,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )
        order2 = order_service.create(
            {
                "target_symbol": "DOT",
                "trading_symbol": "EUR",
                "amount": 200,
                "order_side": "BUY",
                "price": 1.0,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        # Exchange fills both
        portfolio_provider_lookup = \
            self.app.container.portfolio_provider_lookup()
        portfolio_provider_lookup.register_portfolio_provider_for_market(
            "binance"
        )
        portfolio_provider = \
            portfolio_provider_lookup.get_portfolio_provider("binance")
        portfolio_provider.order_amount_filled = None  # fill all

        portfolio_sync_service = \
            self.app.container.portfolio_sync_service()
        portfolio = self.app.container.portfolio_service().find(
            {"market": "binance"}
        )
        portfolio_sync_service.sync_orders(portfolio)

        order1 = order_service.get(order1.id)
        order2 = order_service.get(order2.id)
        self.assertEqual(OrderStatus.CLOSED.value, order1.get_status())
        self.assertEqual(OrderStatus.CLOSED.value, order2.get_status())
        self.assertEqual(100, order1.get_filled())
        self.assertEqual(200, order2.get_filled())


# ------------------------------------------------------------------ #
# Order service sync fix tests (Fix #1–#5)                            #
# ------------------------------------------------------------------ #


class TestSlippagePriceCopied(TestBase):
    """Fix #1: execute_order should copy actual execution price from
    the exchange response so that slippage is captured correctly."""
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {"EUR": 1000}

    def test_execute_order_copies_slippage_price(self):
        """When the exchange fills at a different price, the order
        should reflect the actual execution price."""
        order_executor_lookup = self.app.container.order_executor_lookup()
        order_executor_lookup.register_order_executor_for_market("binance")
        order_executor = order_executor_lookup.get_order_executor("binance")
        order_executor.order_amount_filled = 100
        order_executor.order_status = OrderStatus.CLOSED.value
        # Simulate exchange filling at 0.95 instead of requested 1.0
        order_executor.order_price = 0.95

        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 100,
                "order_side": "BUY",
                "price": 1.0,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )
        self.assertEqual(0.95, order.get_price())
        self.assertEqual(100, order.get_filled())

    def test_execute_order_keeps_original_price_when_none(self):
        """When the exchange does not return a price, the original
        requested price should be preserved."""
        order_executor_lookup = self.app.container.order_executor_lookup()
        order_executor_lookup.register_order_executor_for_market("binance")
        order_executor = order_executor_lookup.get_order_executor("binance")
        order_executor.order_amount_filled = 100
        order_executor.order_status = OrderStatus.CLOSED.value
        # order_price is None by default

        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 100,
                "order_side": "BUY",
                "price": 1.0,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )
        self.assertEqual(1.0, order.get_price())


class TestBuyCancelRestoresEurNotAsset(TestBase):
    """Fix #2: When a BUY order is cancelled/expired/rejected/failed,
    the EUR-denominated size should be restored to the trading symbol
    position, NOT the remaining asset quantity."""
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {"EUR": 1000}

    def _create_open_buy_order(self, amount, price):
        """Helper: create a BUY order that stays OPEN (not executed)."""
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "BTC",
                "trading_symbol": "EUR",
                "amount": amount,
                "order_side": "BUY",
                "price": price,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )
        return order

    def test_buy_order_cancelled_restores_eur_size(self):
        order_service = self.app.container.order_service()
        # Buy 2 BTC at 50000 EUR each = 100000 EUR reserved
        # (but we only have 1000, so let's use realistic numbers)
        order = self._create_open_buy_order(amount=10, price=100)
        # 10 * 100 = 1000 EUR reserved, unallocated should be 0

        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(0, portfolio.get_unallocated())

        # Cancel the order (nothing filled)
        order_service.update(order.id, {
            "status": OrderStatus.CANCELED.value,
            "filled": 0,
            "remaining": 10,
        })

        # Unallocated should be restored to 1000 EUR
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(1000, portfolio.get_unallocated())

        # Trading symbol position should also be 1000 EUR
        position_service = self.app.container.position_service()
        eur_position = position_service.find(
            {"symbol": "EUR", "portfolio": portfolio.id}
        )
        self.assertEqual(1000, eur_position.get_amount())

    def test_buy_order_expired_restores_eur_size(self):
        order_service = self.app.container.order_service()
        order = self._create_open_buy_order(amount=10, price=100)

        order_service.update(order.id, {
            "status": OrderStatus.EXPIRED.value,
            "filled": 0,
            "remaining": 10,
        })

        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(1000, portfolio.get_unallocated())

    def test_buy_order_rejected_restores_eur_size(self):
        order_service = self.app.container.order_service()
        order = self._create_open_buy_order(amount=10, price=100)

        order_service.update(order.id, {
            "status": OrderStatus.REJECTED.value,
            "filled": 0,
            "remaining": 10,
        })

        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(1000, portfolio.get_unallocated())

    def test_buy_order_partial_fill_then_cancelled(self):
        """If 3 out of 10 BTC were filled before cancel, only the
        unfilled portion (7 * 100 = 700 EUR) should be released."""
        order_service = self.app.container.order_service()
        order = self._create_open_buy_order(amount=10, price=100)

        # Partial fill: 3 filled
        order_service.update(order.id, {
            "filled": 3,
            "remaining": 7,
        })

        # Then cancel
        order_service.update(order.id, {
            "status": OrderStatus.CANCELED.value,
            "filled": 3,
            "remaining": 7,
        })

        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})
        # 1000 - 1000 (reserved) + 700 (restored) = 700 unallocated
        self.assertEqual(700, portfolio.get_unallocated())


class TestCheckPendingOrdersNoneGuard(TestBase):
    """Fix #3: check_pending_orders should not crash when
    portfolio_provider.get_order returns None."""
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {"EUR": 1000}

    def test_check_pending_orders_skips_none_external_order(self):
        """When the exchange returns None for get_order, the order
        should be skipped without crashing."""
        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 100,
                "order_side": "BUY",
                "price": 1.0,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        # Register portfolio provider that returns None
        portfolio_provider_lookup = \
            self.app.container.portfolio_provider_lookup()
        portfolio_provider_lookup.register_portfolio_provider_for_market(
            "binance"
        )
        portfolio_provider = \
            portfolio_provider_lookup.get_portfolio_provider("binance")
        portfolio_provider.return_none_for_order = True

        # This should not raise an exception
        order_service.check_pending_orders()

        # Order should remain unchanged
        order = order_service.get(order.id)
        self.assertEqual(OrderStatus.OPEN.value, order.get_status())


class TestBuyOrderAmountChangeSync(TestBase):
    """Fix #4: When the exchange modifies the buy order amount during
    check_pending_orders, the portfolio balance should be reconciled."""
    storage_repo_type = "pandas"
    market_credentials = [
        MarketCredential(
            market="binance",
            api_key="api_key",
            secret_key="secret_key",
        )
    ]
    portfolio_configurations = [
        PortfolioConfiguration(
            market="binance",
            trading_symbol="EUR"
        )
    ]
    external_balances = {"EUR": 1000}

    def test_buy_order_amount_decreased_by_exchange(self):
        """Exchange reduces BUY order amount from 1000 to 999 units.
        The 1 unit * price difference should be released back."""
        order_executor_lookup = self.app.container.order_executor_lookup()
        order_executor_lookup.register_order_executor_for_market("binance")

        order_service = self.app.container.order_service()
        order = order_service.create(
            {
                "target_symbol": "ADA",
                "trading_symbol": "EUR",
                "amount": 1000,
                "order_side": "BUY",
                "price": 1,
                "order_type": "LIMIT",
                "portfolio_id": 1,
            }
        )

        # Order is OPEN, 1000 EUR reserved
        portfolio_service = self.app.container.portfolio_service()
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(0, portfolio.get_unallocated())

        # Exchange fills at reduced amount 999
        portfolio_provider_lookup = \
            self.app.container.portfolio_provider_lookup()
        portfolio_provider_lookup.register_portfolio_provider_for_market(
            "binance"
        )
        portfolio_provider = \
            portfolio_provider_lookup.get_portfolio_provider("binance")
        portfolio_provider.order_amount = 999
        portfolio_provider.order_amount_filled = 999

        order_service.check_pending_orders()

        order = order_service.get(order.id)
        self.assertEqual(999, order.get_amount())
        self.assertEqual(999, order.get_filled())

        # The 1 EUR difference should be back in unallocated
        portfolio = portfolio_service.find({"market": "binance"})
        self.assertEqual(1, portfolio.get_unallocated())

        # Trading symbol position should reflect the released EUR
        position_service = self.app.container.position_service()
        eur_position = position_service.find(
            {"symbol": "EUR", "portfolio": portfolio.id}
        )
        self.assertEqual(1, eur_position.get_amount())
